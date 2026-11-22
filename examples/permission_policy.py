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
KNOWN_TOOLS = frozenset({"Read", "Grep", "Write", "Edit", "BashPreview"})
READ_ONLY_TOOLS = frozenset({"Read", "Grep"})


@dataclass(frozen=True)
class Policy:
    deny: frozenset[str] = frozenset()
    ask: frozenset[str] = frozenset()
    allow: frozenset[str] = frozenset()
    mode: Mode = "manual"
    safe_reads: frozenset[str] = READ_ONLY_TOOLS

    def __post_init__(self):
        if not isinstance(self.mode, str) or self.mode not in {"manual", "read_only", "unattended"}:
            raise ValueError("unsupported teaching mode")
        for field_name in ("deny", "ask", "allow", "safe_reads"):
            values = getattr(self, field_name)
            if not isinstance(values, frozenset) or any(
                    not isinstance(tool, str) or tool not in KNOWN_TOOLS for tool in values):
                raise ValueError(f"{field_name} must be a frozenset of known tool names")
        if not self.safe_reads <= READ_ONLY_TOOLS:
            raise ValueError("safe_reads may contain only Read and Grep")

    def decide(self, tool: str, *, approved_by_user: bool = False) -> Decision:
        if type(approved_by_user) is not bool:
            return "deny"
        if not isinstance(tool, str) or not tool or tool not in KNOWN_TOOLS:
            return "deny"
        if tool in self.deny:
            return "deny"
        # The read-only boundary is immutable: configuration cannot relabel
        # Write/Edit/BashPreview as a safe read.
        if self.mode == "read_only" and tool not in self.safe_reads:
            return "deny"
        if tool in self.ask:
            if self.mode == "unattended":
                return "deny"
            return "allow" if approved_by_user else "ask"
        if tool in self.allow or tool in self.safe_reads:
            return "allow"
        if self.mode == "unattended":
            return "deny"
        return "allow" if approved_by_user else "ask"
