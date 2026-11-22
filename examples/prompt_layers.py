"""Offline prompt assembly demonstration, not Claude Code's internal prompt layout.

Building a prompt is separate from permission policy. This example deliberately
does not execute tools or assume every project file has system-level authority.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class PromptPlan:
    system_blocks: tuple[str, ...]
    contextual_messages: tuple[dict[str, str], ...]
    static_prefix_hash: str


def plan_prompt(base_policy: str, project_rules: str, task: str,
                skill_name: str = "", skill_content: str = "") -> PromptPlan:
    if not base_policy.strip() or not task.strip():
        raise ValueError("base policy and task are required")
    if bool(skill_name) != bool(skill_content):
        raise ValueError("skill name/content must be supplied together")
    # Only the app-owned base policy is treated as a stable system-level block.
    system = (base_policy.strip(),)
    context = []
    if project_rules:
        context.append({
            "role": "user",
            "content": f"Project conventions (review before acting):\n{project_rules}",
        })
    if skill_name:
        context.append({
            "role": "user",
            "content": f"Selected workflow: {skill_name}\n{skill_content}",
        })
    context.append({"role": "user", "content": task})
    fingerprint = hashlib.sha256(
        json.dumps(system, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return PromptPlan(system, tuple(context), fingerprint)


def tool_allowed(requested: str, explicit_allowlist: set[str]) -> bool:
    """Actual authority is checked outside model-generated instructions."""
    return requested in explicit_allowlist
