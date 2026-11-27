"""A small, local handoff journal for teaching context persistence.

Not an encrypted vault, shared database, Claude Code session format or
production event store. Caller must only supply already redacted facts.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

MAX_JOURNAL_BYTES = 64_000
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Handoff:
    task: str
    constraints: tuple[str, ...]
    verified: tuple[str, ...]
    pending: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not isinstance(self.task, str) or not self.task.strip() or len(self.task) > 4000:
            raise ValueError("task must be nonempty bounded text")
        for name in ("constraints", "verified", "pending", "evidence_refs"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) > 64:
                raise ValueError(f"{name} must be a tuple of at most 64 items")
            if any(not isinstance(text, str) or not text.strip() or len(text) > 500
                   for text in values):
                raise ValueError(f"{name} must contain nonempty bounded text")
        if not self.constraints:
            raise ValueError("at least one constraint is required")
        if not (self.pending or self.verified):
            raise ValueError("handoff must contain actual progress")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def encode(h: Handoff) -> bytes:
    h.validate()
    payload = {"schema": 1, "handoff": asdict(h)}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ValueError("journal exceeds 64KB demo limit")
    return raw


def _trusted_path(path: Path) -> Path:
    target = Path(path)
    if (target.is_symlink() or
            any(parent.is_symlink() for parent in (target.parent, *target.parent.parents))):
        raise ValueError("journal must be in a trusted non-symlink directory")
    if not target.parent.is_dir():
        raise ValueError("journal parent directory does not exist")
    return target


def save(path: Path, handoff: Handoff) -> str:
    """Atomically replace a file. Caller is responsible for access control."""
    target = _trusted_path(path)
    data = encode(handoff)
    checksum = hashlib.sha256(data).hexdigest()
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False) as out:
            temp_name = out.name
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return checksum


def load(path: Path, expected_sha256: str) -> Handoff:
    target = _trusted_path(path)
    if not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")
    if not target.is_file() or target.stat().st_size > MAX_JOURNAL_BYTES:
        raise ValueError("journal is missing, not a file, or too large")
    with target.open("rb") as stream:
        raw = stream.read(MAX_JOURNAL_BYTES + 1)
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ValueError("journal exceeds 64KB demo limit")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_sha256):
        raise ValueError("journal checksum mismatch")
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(value, dict) or set(value) != {"schema", "handoff"} or
            type(value["schema"]) is not int or value["schema"] != 1):
        raise ValueError("unsupported schema")
    body = value["handoff"]
    required = {"task", "constraints", "verified", "pending", "evidence_refs"}
    if not isinstance(body, dict) or set(body) != required:
        raise ValueError("unexpected journal fields")
    for field_name in ("constraints", "verified", "pending", "evidence_refs"):
        if not isinstance(body[field_name], list):
            raise ValueError(f"{field_name} must be an array")
    result = Handoff(
        task=body["task"],
        constraints=tuple(body["constraints"]),
        verified=tuple(body["verified"]),
        pending=tuple(body["pending"]),
        evidence_refs=tuple(body["evidence_refs"]),
    )
    result.validate()
    return result
