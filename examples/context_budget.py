"""Offline context-budget planner; NOT Claude Code's compaction algorithm.

Supply actual model/API token counts when available. This module does not
tokenize text or invoke server-side compaction. Thresholds are our choices.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Decision = Literal["continue", "checkpoint", "block"]


@dataclass(frozen=True)
class Budget:
    context_window: int
    reserved_output: int
    headroom: int
    checkpoint_fraction: float = 0.8

    def __post_init__(self):
        if (self.context_window <= 0 or self.reserved_output < 0
            or self.headroom < 0
            or self.reserved_output + self.headroom >= self.context_window):
            raise ValueError("invalid context budget")
        if not 0 < self.checkpoint_fraction < 1:
            raise ValueError("checkpoint_fraction must be between zero and one")

    @property
    def active_input_limit(self) -> int:
        return self.context_window - self.reserved_output - self.headroom

    def decide(self, input_tokens: int) -> Decision:
        if type(input_tokens) is not int or input_tokens < 0:
            raise ValueError("input_tokens must be a nonnegative integer")
        if input_tokens >= self.active_input_limit:
            return "block"
        if input_tokens >= self.active_input_limit * self.checkpoint_fraction:
            return "checkpoint"
        return "continue"


@dataclass(frozen=True)
class Checkpoint:
    """A structured handoff to manually validate before context replacement."""
    goal: str
    constraints: tuple[str, ...]
    verified: tuple[str, ...]
    unfinished: tuple[str, ...]
    references: tuple[str, ...]
    open_questions: tuple[str, ...]

    def __post_init__(self):
        if not self.goal.strip() or not self.constraints:
            raise ValueError("goal and constraints must not be lost")
        if not self.unfinished and not self.verified:
            raise ValueError("checkpoint needs concrete task state")

    def as_dict(self) -> dict[str, object]:
        return {
            "goal": self.goal,
            "constraints": list(self.constraints),
            "verified": list(self.verified),
            "unfinished": list(self.unfinished),
            "references": list(self.references),
            "open_questions": list(self.open_questions),
        }


if __name__ == "__main__":
    # Purely illustrative hypothetical budget; not any model's fixed window.
    b = Budget(context_window=32_000, reserved_output=4_000, headroom=2_000)
    print("active input limit:", b.active_input_limit)
    print("at 21,000 input tokens:", b.decide(21_000))
