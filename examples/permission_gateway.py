"""An offline permission decision and approval-token gateway.

No real tools are executed. Every approval is tied to one exact request,
must be human-originated, and is consumed at most once. Demonstrates
the difference between 'ask' and actually granting execution authority.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from permission_policy import Policy


@dataclass(frozen=True)
class ToolRequest:
    tool: str
    arguments: dict[str, Any]

    def fingerprint(self) -> str:
        if not isinstance(self.arguments, dict):
            raise ValueError("tool arguments must be an object")
        data = json.dumps({"tool": self.tool, "arguments": self.arguments},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Approval:
    """Created by the host approval UI, never accepted from model tool input."""
    request_digest: str
    approved_by: str
    decision: str


class PermissionGateway:
    def __init__(self, policy: Policy):
        self.policy = policy
        self._consumed: set[str] = set()

    def evaluate(self, req: ToolRequest, approval: Approval | None = None) -> tuple[str, str]:
        digest = req.fingerprint()
        baseline = self.policy.decide(req.tool, approved_by_user=False)
        if baseline == "deny":
            return "deny", "policy denies this action"
        if baseline == "allow":
            return "allow", "policy grants the action"
        if approval is None:
            return "ask", "a human must approve this exact request"
        if (approval.decision != "approve"
                or not approval.approved_by.strip()
                or approval.request_digest != digest):
            return "deny", "missing, refused or mismatched approval"
        if digest in self._consumed:
            return "deny", "approval already consumed"
        # Same request, same policy, fresh human approval: commit the decision.
        if self.policy.decide(req.tool, approved_by_user=True) != "allow":
            return "deny", "current policy does not permit approval"
        self._consumed.add(digest)
        return "allow", "single-use human approval accepted"


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
