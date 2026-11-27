"""Evidence-based task completion gates; no language-pattern heuristics.

The actor string is a teaching label only. Production approval must come from
an authenticated, independently authorized identity provider.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class TaskContract:
    required_checks: tuple[str, ...]
    max_steps: int = 30
    requires_human_approval: bool = False

    def __post_init__(self):
        if (not isinstance(self.required_checks, tuple) or
                not 1 <= len(self.required_checks) <= 64):
            raise ValueError("required_checks must be a tuple of 1–64 names")
        if any(not isinstance(x, str) or not x.strip() or len(x) > 128
               for x in self.required_checks):
            raise ValueError("check names must be nonempty bounded text")
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("required checks must be unique")
        if type(self.max_steps) is not int or not 1 <= self.max_steps <= 100_000:
            raise ValueError("max_steps must be an integer from 1 to 100000")
        if type(self.requires_human_approval) is not bool:
            raise ValueError("requires_human_approval must be a boolean")


@dataclass(frozen=True)
class CheckEvidence:
    passed: bool
    artifact: str

    def __post_init__(self):
        if type(self.passed) is not bool:
            raise ValueError("passed must be a boolean")
        if not isinstance(self.artifact, str) or len(self.artifact) > 500:
            raise ValueError("artifact must be bounded text")
        if self.passed and not self.artifact.strip():
            raise ValueError("a passing check must cite evidence")


@dataclass
class CompletionGate:
    contract: TaskContract
    steps: int = 0
    checks: dict[str, CheckEvidence] = field(default_factory=dict)
    human_decision: bool | None = None

    def __post_init__(self):
        if not isinstance(self.contract, TaskContract):
            raise ValueError("contract must be a TaskContract")
        if type(self.steps) is not int or not 0 <= self.steps <= self.contract.max_steps:
            raise ValueError("steps must be within the contract budget")
        if not isinstance(self.checks, dict):
            raise ValueError("checks must be a mapping")
        if self.human_decision is not None and type(self.human_decision) is not bool:
            raise ValueError("human_decision must be true, false, or None")
        for name, evidence in self.checks.items():
            if name not in self.contract.required_checks or not isinstance(evidence, CheckEvidence):
                raise ValueError("checks contain an uncontracted or malformed result")

    def record_step(self) -> None:
        if self.human_decision is False:
            raise RuntimeError("human approval was denied")
        if self.steps >= self.contract.max_steps:
            raise RuntimeError("step budget exhausted")
        self.steps += 1

    def record_check(self, name: str, passed: bool, artifact: str) -> None:
        if self.human_decision is False:
            raise RuntimeError("human approval was denied")
        if name not in self.contract.required_checks:
            raise ValueError("check is not part of the acceptance contract")
        self.checks[name] = CheckEvidence(passed, artifact)

    def record_human_decision(self, approved: bool, actor: str) -> None:
        if actor != "human":
            raise PermissionError("only a human decision source can approve")
        if type(approved) is not bool:
            raise ValueError("approved must be a boolean")
        self.human_decision = approved

    def decide(self) -> str:
        if self.human_decision is False:
            return "blocked"
        incomplete = any(name not in self.checks or not self.checks[name].passed
                         for name in self.contract.required_checks)
        if incomplete:
            return "budget_exhausted" if self.steps >= self.contract.max_steps else "continue"
        if self.contract.requires_human_approval and self.human_decision is not True:
            return "await_approval"
        return "ready"


@dataclass
class EvaluatorLoop:
    """Bounded evaluator-optimizer loop driven by finite measured scores."""
    threshold: float
    max_rounds: int
    scores: list[float] = field(default_factory=list)

    def __post_init__(self):
        if (isinstance(self.threshold, bool) or
                not isinstance(self.threshold, (int, float)) or
                not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1):
            raise ValueError("threshold must be a finite number from 0 to 1")
        if type(self.max_rounds) is not int or not 1 <= self.max_rounds <= 10_000:
            raise ValueError("max_rounds must be an integer from 1 to 10000")
        if not isinstance(self.scores, list) or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or
                not math.isfinite(x) or not 0 <= x <= 1 for x in self.scores):
            raise ValueError("scores must be finite numbers from 0 to 1")
        if len(self.scores) > self.max_rounds:
            raise ValueError("scores exceed the round budget")

    def record(self, score: float) -> str:
        if len(self.scores) >= self.max_rounds:
            raise RuntimeError("evaluation round budget exhausted")
        if (isinstance(score, bool) or not isinstance(score, (int, float)) or
                not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("score must be a finite number between zero and one")
        self.scores.append(float(score))
        if score >= self.threshold:
            return "accepted"
        return "continue" if len(self.scores) < self.max_rounds else "budget_exhausted"


if __name__ == "__main__":
    gate = CompletionGate(TaskContract(
        ("unit_tests", "diff_review"), max_steps=8, requires_human_approval=True
    ))
    gate.record_check("unit_tests", True, "pytest: 42 passed")
    gate.record_check("diff_review", True, "review: no blocking findings")
    print(gate.decide())  # await_approval
    gate.record_human_decision(True, "human")
    print(gate.decide())  # ready
