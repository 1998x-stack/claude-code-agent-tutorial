"""A deterministic task dependency board for learning agent planning.

This is not a Claude Code TodoWrite implementation. It models explicit state,
DAG prerequisites and terminal failures outside of an LLM context window.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

State = Literal["pending", "in_progress", "completed", "failed"]


@dataclass
class Task:
    id: str
    title: str
    depends_on: tuple[str, ...] = ()
    status: State = "pending"
    evidence: str = ""


@dataclass
class TaskBoard:
    tasks: dict[str, Task] = field(default_factory=dict)

    def add(self, task_id: str, title: str, dependencies: tuple[str, ...] = ()) -> None:
        if not task_id.isidentifier() or not title.strip():
            raise ValueError("task id must be identifier, title cannot be empty")
        if task_id in self.tasks:
            raise ValueError("duplicate task id")
        if len(set(dependencies)) != len(dependencies):
            raise ValueError("duplicate dependency")
        self.tasks[task_id] = Task(task_id, title, dependencies)

    def validate(self) -> None:
        """Check missing dependencies and cycles using three-color DFS."""
        marks: dict[str, int] = {}
        def visit(node: str) -> None:
            if node not in self.tasks:
                raise ValueError(f"unknown dependency: {node}")
            if marks.get(node) == 1:
                raise ValueError("cycle in task dependencies")
            if marks.get(node) == 2:
                return
            marks[node] = 1
            for dep in self.tasks[node].depends_on:
                visit(dep)
            marks[node] = 2
        for node in self.tasks:
            visit(node)

    def ready(self) -> list[str]:
        self.validate()
        return [
            t.id for t in self.tasks.values()
            if t.status == "pending"
            and all(self.tasks[d].status == "completed" for d in t.depends_on)
        ]

    def start(self, task_id: str) -> None:
        self.validate()
        if task_id not in self.ready():
            raise ValueError("task is not ready or already started")
        if any(t.status == "in_progress" for t in self.tasks.values()):
            raise ValueError("one in-progress task at a time in this teaching board")
        self.tasks[task_id].status = "in_progress"

    def complete(self, task_id: str, evidence: str) -> None:
        task = self.tasks[task_id]
        if task.status != "in_progress":
            raise ValueError("only an in-progress task can complete")
        if not evidence.strip():
            raise ValueError("completion needs verification evidence")
        task.status = "completed"
        task.evidence = evidence

    def fail(self, task_id: str, reason: str) -> None:
        task = self.tasks[task_id]
        if task.status != "in_progress" or not reason.strip():
            raise ValueError("failure requires active task and explanation")
        task.status = "failed"
        task.evidence = reason

    def snapshot(self) -> list[dict[str, object]]:
        self.validate()
        return [{
            "id": t.id,
            "title": t.title,
            "depends_on": list(t.depends_on),
            "status": t.status,
            "evidence": t.evidence,
        } for t in self.tasks.values()]


if __name__ == "__main__":
    board = TaskBoard()
    board.add("inspect", "Inspect failing test")
    board.add("patch", "Create minimal change", ("inspect",))
    board.add("verify", "Run focused tests", ("patch",))
    board.start("inspect")
    board.complete("inspect", "Observed assertion and traceback")
    print(board.ready())  # ['patch']
