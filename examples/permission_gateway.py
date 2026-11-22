"""An offline permission decision and approval-token gateway.

No real tools are executed. An approval is bound to one exact request and is
consumed once per process. This class cannot authenticate the approver or
persist replay state; the host must supply both in production.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from permission_policy import Policy

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ToolRequest:
    tool: str
    arguments: dict[str, Any]

    def fingerprint(self) -> str:
        if not isinstance(self.tool, str) or not self.tool:
            raise ValueError("tool name must be nonempty text")
        if not isinstance(self.arguments, dict):
            raise ValueError("tool arguments must be an object")
        data = json.dumps(
            {"tool": self.tool, "arguments": self.arguments},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Approval:
    """Host-created approval data; approved_by is descriptive, not authenticated.""" 
    request_digest: str
    approved_by: str
    decision: str


class PermissionGateway:
    def __init__(self, policy: Policy):
        if not isinstance(policy, Policy):
            raise ValueError("policy must be a Policy")
        self.policy = policy
        self._consumed: set[str] = set()

    def evaluate(self, req: ToolRequest, approval: Approval | None = None) -> tuple[str, str]:
        if not isinstance(req, ToolRequest):
            return "deny", "invalid tool request"
        try:
            digest = req.fingerprint()
        except (TypeError, ValueError):
            return "deny", "invalid tool request"
        baseline = self.policy.decide(req.tool, approved_by_user=False)
        if baseline == "deny":
            return "deny", "policy denies this action"
        if baseline == "allow":
            return "allow", "policy grants the action"
        if approval is None:
            return "ask", "a human must approve this exact request"
        if not isinstance(approval, Approval):
            return "deny", "invalid approval object"
        if (not isinstance(approval.request_digest, str) or
                not _DIGEST.fullmatch(approval.request_digest) or
                not isinstance(approval.approved_by, str) or
                not approval.approved_by.strip() or
                approval.decision not in {"approve", "deny"} or
                approval.decision != "approve" or
                approval.request_digest != digest):
            return "deny", "missing, refused or mismatched approval"
        if digest in self._consumed:
            return "deny", "approval already consumed in this process"
        if self.policy.decide(req.tool, approved_by_user=True) != "allow":
            return "deny", "current policy does not permit approval"
        self._consumed.add(digest)
        return "allow", "single-use approval data accepted; identity is host responsibility"


def demo() -> None:
    req = ToolRequest("Edit", {"path": "docs/intro.md", "content": "new text"})
    gateway = PermissionGateway(Policy(ask=frozenset({"Edit"})))
    print("before approval:", gateway.evaluate(req))
    print("with approval:", gateway.evaluate(req, Approval(
        req.fingerprint(), approved_by="local-user", decision="approve"
    )))
    print("replayed approval:", gateway.evaluate(req, Approval(
        req.fingerprint(), approved_by="local-user", decision="approve"
    )))


if __name__ == "__main__":
    demo()
