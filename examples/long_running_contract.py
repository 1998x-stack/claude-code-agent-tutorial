"""Durable, fail-closed feature ledger for long-running agent education.

A deterministic teaching coordinator, NOT Claude Code implementation, secure
identity system, OS sandbox, or remote worker. Only a trusted external
evaluator should be allowed to call verify() in a real application.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile

STATUSES = {"pending", "in_progress", "blocked", "passed"}
MAX_FEATURES = 128
MAX_TEXT = 500

@dataclass
class Feature:
    ident: str
    goal: str
    acceptance: str
    status: str = "pending"
    evidence: str = ""
    attempts: int = 0

    def validate(self) -> None:
        if (not self.ident.isascii() or
            not self.ident.replace("-", "").replace("_", "").isalnum() or
            not (1 <= len(self.ident) <= 48)):
            raise ValueError("feature ID must be safe and bounded")
        if not (self.goal.strip() and self.acceptance.strip()):
            raise ValueError("feature goal and acceptance criteria are required")
        if len(self.goal) > MAX_TEXT or len(self.acceptance) > MAX_TEXT:
            raise ValueError("feature text is too long")
        if self.status not in STATUSES:
            raise ValueError("unknown feature status")
        if not isinstance(self.attempts, int) or self.attempts < 0:
            raise ValueError("invalid attempt count")
        if self.status == "passed" and not self.evidence.strip():
            raise ValueError("passed requires independent evidence")
        if self.status != "passed" and self.evidence:
            raise ValueError("unverified feature cannot hold passing evidence")

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
        if (not self.project.strip() or not self.workspace_revision.strip() or
            len(self.features) == 0 or len(self.features) > MAX_FEATURES or
            not isinstance(self.max_attempts, int) or
            not 1 <= self.max_attempts <= 20):
            raise ValueError("invalid ledger")
        ids = [f.ident for f in self.features]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate feature ID")
        for item in self.features:
            item.validate()
        if not isinstance(self.stopped, bool) or not isinstance(self.version, int) or self.version < 0:
            raise ValueError("invalid ledger status")
        if any(not x.strip() or len(x) > MAX_TEXT for x in self.steering):
            raise ValueError("invalid steering instruction")
        if len(self.steering) > 64:
            raise ValueError("steering log too long")

    def _get(self, ident: str) -> Feature:
        for item in self.features:
            if item.ident == ident:
                return item
        raise KeyError(ident)

    def next_feature(self) -> Feature | None:
        if self.stopped or any(f.status == "blocked" for f in self.features):
            return None
        return next((f for f in self.features if f.status in {"pending", "in_progress"}), None)

    def start(self, ident: str) -> None:
        if self.stopped:
            raise PermissionError("kill switch is engaged")
        if any(f.status == "blocked" for f in self.features):
            raise RuntimeError("blocked feature requires external review")
        item = self._get(ident)
        if item.status not in {"pending", "in_progress"}:
            raise ValueError("only pending or active work can start")
        if item.attempts >= self.max_attempts:
            item.status = "blocked"
            raise RuntimeError("feature attempt budget exhausted")
        item.status = "in_progress"
        item.attempts += 1
        self.version += 1

    def verify(self, ident: str, passed: bool, artifact: str, *, actor: str) -> None:
        """Only accept verdicts with checkable external artifacts.

        'actor' is a teaching label, NOT an authentication mechanism.
        """
        if self.stopped:
            raise PermissionError("kill switch is engaged")
        if actor != "evaluator":
            raise PermissionError("a generator cannot attest its own feature")
        item = self._get(ident)
        if item.status != "in_progress":
            raise ValueError("feature was not under evaluation")
        if not isinstance(passed, bool):
            raise ValueError("passed must be a real boolean")
        if passed:
            if not artifact.strip() or len(artifact) > MAX_TEXT:
                raise ValueError("passing evidence is required")
            item.status = "passed"
            item.evidence = artifact.strip()
        else:
            item.status = "blocked" if item.attempts >= self.max_attempts else "pending"
            item.evidence = ""
        self.version += 1

    def steer(self, instruction: str, *, actor: str) -> None:
        if actor != "human":
            raise PermissionError("steering must come from an authorized human")
        if self.stopped:
            raise PermissionError("cannot steer a stopped task")
        if not instruction.strip() or len(instruction) > MAX_TEXT:
            raise ValueError("invalid steering note")
        if len(self.steering) >= 64:
            raise ValueError("steering log is full")
        self.steering.append(instruction.strip())
        self.version += 1

    def stop(self, *, actor: str) -> None:
        if actor != "human":
            raise PermissionError("kill switch must come from an authorized human")
        self.stopped = True
        self.version += 1

    @property
    def complete(self) -> bool:
        return bool(self.features) and all(f.status == "passed" for f in self.features) and not self.stopped

    def to_bytes(self) -> bytes:
        self.__post_init__()
        return json.dumps({"schema": 1, "ledger": asdict(self)},
                          ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")

    def checkpoint(self, path: Path) -> str:
        """Atomically replace one caller-designated local checkpoint file.

        No symlinks; caller must provide directory permissions and workspace
        containment. A checksum must be kept independently, not just here.
        """
        path = Path(path)
        if not path.parent.is_dir() or path.is_symlink():
            raise ValueError("invalid checkpoint location")
        raw = self.to_bytes()
        if len(raw) > 128_000:
            raise ValueError("checkpoint too large")
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
        if path.is_symlink():
            raise ValueError("checkpoint symlink is forbidden")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("checkpoint checksum mismatch")
        if len(raw) > 128_000:
            raise ValueError("checkpoint too large")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict) or set(decoded) != {"schema", "ledger"} or decoded["schema"] != 1:
            raise ValueError("unsupported checkpoint schema")
        obj = decoded["ledger"]
        expected = {"project", "workspace_revision", "features", "max_attempts",
                    "stopped", "steering", "version"}
        if not isinstance(obj, dict) or set(obj) != expected:
            raise ValueError("unexpected ledger fields")
        features = []
        for row in obj["features"]:
            if set(row) != {"ident", "goal", "acceptance", "status", "evidence", "attempts"}:
                raise ValueError("unexpected feature fields")
            features.append(Feature(**row))
        result = cls(project=obj["project"],
                     workspace_revision=obj["workspace_revision"],
                     features=features, max_attempts=obj["max_attempts"],
                     stopped=obj["stopped"], steering=obj["steering"],
                     version=obj["version"])
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
    task.verify("read", True, "read fixture SHA256:abc", actor="evaluator")
    print("next work:", task.next_feature().ident)
