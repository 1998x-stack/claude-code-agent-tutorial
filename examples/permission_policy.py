"""A small, fail-closed teaching permission policy.

Not Claude Code's rule parser. Only whole tool names are supported: no Bash
patterns, wildcard parsing, hooks, classifier, critical-path recognition or
managed settings. The most restrictive matching rule wins.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Decision = Literal["allow", "ask", "deny"]
Mode = Literal["manual", "read_only", "unattended"]


@dataclass(frozen=True)
class Policy:
    deny: frozenset[str] = frozenset()
    ask: frozenset[str] = frozenset()
    allow: frozenset[str] = frozenset()
    mode: Mode = "manual"
    safe_reads: frozenset[str] = frozenset({"Read", "Grep"})

    def decide(self, tool: str, *, approved_by_user: bool = False) -> Decision:
        if not isinstance(tool, str) or not tool:
            return "deny"
        if self.mode not in ("manual", "read_only", "unattended"):
            raise ValueError("unsupported teaching mode")
        # This demo accepts only a known set of tools; no name-pattern parser.
        known = {"Read", "Grep", "Write", "Edit", "BashPreview"}
        if tool not in known:
            return "deny"
        if tool in self.deny:
            return "deny"
        # In this *teaching* read-only mode, explicit ask cannot override
        # the resource boundary, even with a user confirmation.
        if self.mode == "read_only" and tool not in self.safe_reads:
            return "deny"
        if tool in self.ask:
            # An explicit ask requires a fresh user decision, even when allow
            # contains the same tool. A prior approval is scoped to this call.
            if self.mode == "unattended":
                return "deny"
            return "allow" if approved_by_user else "ask"
        if self.mode == "read_only" and tool not in self.safe_reads:
            return "deny"
        if tool in self.allow or tool in self.safe_reads:
            return "allow"
        if self.mode == "unattended":
            return "deny"
        return "allow" if approved_by_user else "ask"
