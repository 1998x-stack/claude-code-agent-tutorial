"""Teaching-only delegation envelope: explicit inputs and narrowed capabilities.

No model calls, no subprocess, no filesystem privileges and no automatic
permissions. A child never gets the parent's conversation by default here.
Claude Code may use different context inheritance depending on agent type.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Delegation:
    name: str
    goal: str
    evidence_refs: tuple[str, ...]
    allowed_tools: frozenset[str]
    max_turns: int


@dataclass(frozen=True)
class Finding:
    agent: str
    summary: str
    sources: tuple[str, ...]
    unresolved: tuple[str, ...]


def delegate(
    *, name: str, goal: str, refs: tuple[str, ...],
    parent_allowed: frozenset[str],
    requested_tools: frozenset[str],
    budget: int,
) -> Delegation:
    if not name.isidentifier() or not goal.strip():
        raise ValueError("child name and goal required")
    if not 1 <= budget <= 20:
        raise ValueError("child must have bounded turns")
    if not requested_tools.issubset(parent_allowed):
        raise PermissionError("child cannot receive more tools than parent")
    if not refs or any(not p.strip() for p in refs):
        raise ValueError("child needs explicit references to inspect")
    return Delegation(name, goal, refs, requested_tools, budget)


def validate_result(job: Delegation, result: Finding) -> None:
    if result.agent != job.name or not result.summary.strip():
        raise ValueError("child result identity or summary mismatch")
    if not set(result.sources).issubset(job.evidence_refs):
        raise ValueError("result contains undeclared evidence references")
