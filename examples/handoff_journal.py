"""A small, local handoff journal for teaching context persistence.

Not an encrypted vault, shared database, Claude Code session format or
production event store. Caller must only supply already redacted facts.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class Handoff:
    task: str
    constraints: tuple[str, ...]
    verified: tuple[str, ...]
    pending: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.task.strip() or not self.constraints:
            raise ValueError("task and constraints must be present")
        if not (self.pending or self.verified):
            raise ValueError("handoff must contain actual progress")
        if any(not text.strip() for text in self.constraints + self.verified +
               self.pending + self.evidence_refs):
            raise ValueError("blank handoff field")


def encode(h: Handoff) -> bytes:
    h.validate()
    # Stable schema and checksum allow accidental corruption to be detected.
    payload = {"schema": 1, "handoff": asdict(h)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def save(path: Path, handoff: Handoff) -> str:
    """Atomically replace a file. Caller is responsible for access control."""
    target = Path(path)
    if not target.parent.is_dir() or target.is_symlink():
        raise ValueError("invalid journal location")
    data = encode(handoff)
    if len(data) > 64_000:
        raise ValueError("journal exceeds 64KB demo limit")
    checksum = hashlib.sha256(data).hexdigest()
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, delete=False
        ) as out:
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
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("journal checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("unsupported schema")
    body = value["handoff"]
    required = {"task", "constraints", "verified", "pending", "evidence_refs"}
    if set(body) != required:
        raise ValueError("unexpected journal fields")
    result = Handoff(
        task=body["task"],
        constraints=tuple(body["constraints"]),
        verified=tuple(body["verified"]),
        pending=tuple(body["pending"]),
        evidence_refs=tuple(body["evidence_refs"]),
    )
    result.validate()
    return result
