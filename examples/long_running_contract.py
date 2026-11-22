"""Fail-closed feature ledger for long-running-agent education.

This is a single-writer teaching coordinator, NOT Claude Code internals, a
secure identity system, an OS sandbox, or a remote worker. The caller must
authenticate the evaluator and independently verify every evidence reference.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

STATUSES = {"pending", "in_progress", "blocked", "passed"}
MAX_FEATURES = 128
MAX_TEXT = 500
MAX_CHECKPOINT_BYTES = 128_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class Feature:
    ident: str
    goal: str
    acceptance: str
    status: str = "pending"
    evidence: str = ""
    attempts: int = 0

    def validate(self) -> None:
        if not isinstance(self.ident, str):
            raise ValueError("feature ID must be text")
        if (not self.ident.isascii() or
                not self.ident.replace("-", "").replace("_", "").isalnum() or
                not 1 <= len(self.ident) <= 48):
            raise ValueError("feature ID must be safe and bounded")
        for name, value in (("goal", self.goal), ("acceptance", self.acceptance),
                            ("evidence", self.evidence)):
            if not isinstance(value, str):
                raise ValueError(f"{name} must be text")
            if len(value) > MAX_TEXT:
                raise ValueError(f"{name} is too long")
        if not self.goal.strip() or not self.acceptance.strip():
            raise ValueError("feature goal and acceptance criteria are required")
        if not isinstance(self.status, str) or self.status not in STATUSES:
            raise ValueError("unknown feature status")
        if type(self.attempts) is not int or self.attempts < 0:
            raise ValueError("invalid attempt count")
        if self.status == "passed":
            if not self.evidence.strip() or self.attempts < 1:
                raise ValueError("passed requires an attempt and an evidence reference")
        elif self.evidence:
            raise ValueError("unverified feature cannot hold passing evidence")
        if self.status == "in_progress" and self.attempts < 1:
            raise ValueError("in-progress feature must have a started attempt")


@dataclass
class FeatureLedger:
    project: str
    workspace_revision: str
    features: list[Feature]
    max_attempts: int = 3
    stopped: bool = False
    steering: list[str] = field(default_factory=list)
    version: int = 0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.project, str) or not self.project.strip() or len(self.project) > 128:
            raise ValueError("project must be nonempty bounded text")
        if (not isinstance(self.workspace_revision, str) or
                not self.workspace_revision.strip() or len(self.workspace_revision) > 256):
            raise ValueError("workspace revision must be nonempty bounded text")
        if not isinstance(self.features, list) or not 1 <= len(self.features) <= MAX_FEATURES:
            raise ValueError("feature list must contain 1–128 items")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 20:
            raise ValueError("max_attempts must be an integer from 1 to 20")
        if type(self.stopped) is not bool:
            raise ValueError("stopped must be a boolean")
        if type(self.version) is not int or self.version < 0:
            raise ValueError("version must be a nonnegative integer")
        if not isinstance(self.steering, list) or len(self.steering) > 64:
            raise ValueError("steering must be a list of at most 64 notes")
        for note in self.steering:
            if not isinstance(note, str) or not note.strip() or len(note) > MAX_TEXT:
                raise ValueError("invalid steering note")
        if any(not isinstance(item, Feature) for item in self.features):
            raise ValueError("features must contain Feature objects")
        ids = [item.ident for item in self.features]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate feature ID")
        for item in self.features:
            item.validate()
            if item.attempts > self.max_attempts:
                raise ValueError("feature attempts exceed the ledger budget")
            if item.status == "pending" and item.attempts >= self.max_attempts:
                raise ValueError("exhausted feature cannot remain pending")

    def _get(self, ident: str) -> Feature:
        for item in self.features:
            if item.ident == ident:
                return item
        raise KeyError(ident)

    def next_feature(self) -> Feature | None:
        # Deliberately fail-stop: any blocked item requires review before the
        # single-writer coordinator schedules more project work.
        if self.stopped or any(f.status == "blocked" for f in self.features):
            return None
        return next((f for f in self.features
                     if f.status in {"pending", "in_progress"}), None)

    def start(self, ident: str) -> None:
        if self.stopped:
            raise PermissionError("kill switch is engaged")
        if any(f.status == "blocked" for f in self.features):
            raise RuntimeError("blocked feature requires external review")
        item = self._get(ident)
        if item.status == "in_progress":
            # Resume the same single-writer attempt after reading a checkpoint;
            # do not charge a second attempt for an idempotent resume.
            return
        if item.status != "pending":
            raise ValueError("only pending work can start")
        if item.attempts >= self.max_attempts:
            item.status = "blocked"
            self.version += 1
            raise RuntimeError("feature attempt budget exhausted")
        item.status = "in_progress"
        item.attempts += 1
        self.version += 1

    def verify(self, ident: str, passed: bool, artifact: str, *, actor: str) -> None:
        """Record an externally produced verdict and opaque evidence reference.

        This method validates shape only. It does not open a report, run tests,
        or authenticate actor; the trusted caller must do those things.
        """
        if self.stopped:
            raise PermissionError("kill switch is engaged")
        if actor != "evaluator":
            raise PermissionError("a generator cannot attest its own feature")
        if type(passed) is not bool:
            raise ValueError("passed must be a real boolean")
        if not isinstance(artifact, str) or len(artifact) > MAX_TEXT:
            raise ValueError("evidence reference must be bounded text")
        item = self._get(ident)
        if item.status != "in_progress":
            raise ValueError("feature was not under evaluation")
        if passed:
            if not artifact.strip():
                raise ValueError("passing evidence reference is required")
            item.status = "passed"
            item.evidence = artifact.strip()
        else:
            item.status = "blocked" if item.attempts >= self.max_attempts else "pending"
            item.evidence = ""
        self.version += 1

    def steer(self, instruction: str, *, actor: str) -> None:
        """Append a human note; a separate planner must interpret it.

        This teaching ledger does not itself reorder features or rewrite the
        task contract. actor is a label, not identity authentication.
        """
        if actor != "human":
            raise PermissionError("steering must come from an authorized human")
        if self.stopped:
            raise PermissionError("cannot steer a stopped task")
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > MAX_TEXT:
            raise ValueError("invalid steering note")
        if len(self.steering) >= 64:
            raise ValueError("steering log is full")
        self.steering.append(instruction.strip())
        self.version += 1

    def stop(self, *, actor: str) -> None:
        if actor != "human":
            raise PermissionError("kill switch must come from an authorized human")
        if not self.stopped:
            self.stopped = True
            self.version += 1

    @property
    def complete(self) -> bool:
        return (bool(self.features) and
                all(f.status == "passed" for f in self.features) and
                not self.stopped)

    def to_bytes(self) -> bytes:
        self.validate()
        raw = json.dumps(
            {"schema": 1, "ledger": asdict(self)},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        if len(raw) > MAX_CHECKPOINT_BYTES:
            raise ValueError("checkpoint too large")
        return raw

    def checkpoint(self, path: Path) -> str:
        """Atomically replace a local file in a trusted, caller-owned directory.

        Rejects a symlink at the destination and symlinked parent components.
        This is not race-resistant against a hostile filesystem or a durable
        database. Store the digest independently.
        """
        path = Path(path)
        if (not path.parent.is_dir() or path.is_symlink() or
                any(parent.is_symlink() for parent in (path.parent, *path.parent.parents))):
            raise ValueError("checkpoint must be in a trusted non-symlink directory")
        raw = self.to_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        tmp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as f:
                tmp_name = f.name
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return digest

    @classmethod
    def resume(cls, path: Path, expected_sha256: str, *,
               current_workspace_revision: str) -> "FeatureLedger":
        path = Path(path)
        if (path.is_symlink() or
                any(parent.is_symlink() for parent in (path.parent, *path.parent.parents))):
            raise ValueError("checkpoint symlink is forbidden")
        if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
            raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")
        if not isinstance(current_workspace_revision, str):
            raise ValueError("current workspace revision must be text")
        if not path.is_file() or path.stat().st_size > MAX_CHECKPOINT_BYTES:
            raise ValueError("checkpoint is missing, not a file, or too large")
        with path.open("rb") as stream:
            raw = stream.read(MAX_CHECKPOINT_BYTES + 1)
        if len(raw) > MAX_CHECKPOINT_BYTES:
            raise ValueError("checkpoint too large")
        digest = hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(digest, expected_sha256):
            raise ValueError("checkpoint checksum mismatch")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result

        decoded = json.loads(raw, object_pairs_hook=unique_object)
        if (not isinstance(decoded, dict) or set(decoded) != {"schema", "ledger"} or
                type(decoded["schema"]) is not int or decoded["schema"] != 1):
            raise ValueError("unsupported checkpoint schema")
        obj = decoded["ledger"]
        expected = {"project", "workspace_revision", "features", "max_attempts",
                    "stopped", "steering", "version"}
        if not isinstance(obj, dict) or set(obj) != expected:
            raise ValueError("unexpected ledger fields")
        if not isinstance(obj["features"], list):
            raise ValueError("features must be a list")
        features = []
        for row in obj["features"]:
            feature_fields = {"ident", "goal", "acceptance", "status", "evidence", "attempts"}
            if not isinstance(row, dict) or set(row) != feature_fields:
                raise ValueError("unexpected feature fields")
            features.append(Feature(**row))
        result = cls(
            project=obj["project"], workspace_revision=obj["workspace_revision"],
            features=features, max_attempts=obj["max_attempts"],
            stopped=obj["stopped"], steering=obj["steering"], version=obj["version"],
        )
        if result.workspace_revision != current_workspace_revision:
            raise ValueError("workspace revision changed; revalidate before continuing")
        return result


if __name__ == "__main__":
    task = FeatureLedger("demo", "fixture-r1", [
        Feature("read", "Read file", "File contents verified"),
        Feature("test", "Run tests", "Acceptance suite passes"),
    ])
    print("first work:", task.next_feature().ident)
    task.start("read")
    task.verify("read", True, "external-report://read/sha256:abc", actor="evaluator")
    print("next work:", task.next_feature().ident)
