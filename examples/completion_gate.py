"""Evidence-based task completion gates; no language-pattern heuristics."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskContract:
    required_checks: tuple[str, ...]
    max_steps: int = 30
    requires_human_approval: bool = False

    def __post_init__(self):
        if not self.required_checks or len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("required checks must be nonempty and unique")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")


@dataclass(frozen=True)
class CheckEvidence:
    passed: bool
    artifact: str


@dataclass
class CompletionGate:
    contract: TaskContract
    steps: int = 0
    checks: dict[str, CheckEvidence] = field(default_factory=dict)
    human_decision: bool | None = None

    def record_step(self) -> None:
        if self.steps >= self.contract.max_steps:
            raise RuntimeError("step budget exhausted")
        self.steps += 1

    def record_check(self, name: str, passed: bool, artifact: str) -> None:
        if name not in self.contract.required_checks:
            raise ValueError("check is not part of the acceptance contract")
        if passed and not artifact.strip():
            raise ValueError("a passing check must cite evidence")
        self.checks[name] = CheckEvidence(bool(passed), artifact.strip())

    def record_human_decision(self, approved: bool, actor: str) -> None:
        if actor != "human":
            raise PermissionError("only a human decision source can approve")
        self.human_decision = bool(approved)

    def decide(self) -> str:
        if self.human_decision is False:
            return "blocked"
        if self.steps >= self.contract.max_steps:
            return "budget_exhausted"
        if any(name not in self.checks or not self.checks[name].passed
               for name in self.contract.required_checks):
            return "continue"
        if self.contract.requires_human_approval and self.human_decision is not True:
            return "await_approval"
        return "ready"


@dataclass
class EvaluatorLoop:
    """Bounded evaluator-optimizer loop driven by measured scores."""
    threshold: float
    max_rounds: int
    scores: list[float] = field(default_factory=list)

    def __post_init__(self):
        if not 0 <= self.threshold <= 1 or self.max_rounds < 1:
            raise ValueError("invalid quality threshold or round budget")

    def record(self, score: float) -> str:
        if len(self.scores) >= self.max_rounds:
            raise RuntimeError("evaluation round budget exhausted")
        if not 0 <= score <= 1:
            raise ValueError("score must be between zero and one")
        self.scores.append(score)
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
