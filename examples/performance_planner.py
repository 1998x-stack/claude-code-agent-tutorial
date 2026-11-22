"""Deterministic performance planning with dependency-aware scheduling.

Durations, normalized costs and quality scores are supplied benchmark inputs.
The planner does not call models, tools, APIs or infer vendor pricing.
"""
from __future__ import annotations
from dataclasses import dataclass
import heapq


@dataclass(frozen=True)
class WorkItem:
    name: str
    duration_ms: int
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduledItem:
    name: str
    worker: int
    start_ms: int
    end_ms: int


def schedule(items: tuple[WorkItem, ...], max_workers: int) -> tuple[ScheduledItem, ...]:
    if type(max_workers) is not int or max_workers < 1:
        raise ValueError("max_workers must be a positive integer")
    by_name = {item.name: item for item in items}
    if len(by_name) != len(items) or not items:
        raise ValueError("work item names must be unique and nonempty")
    for item in items:
        if not item.name or type(item.duration_ms) is not int or item.duration_ms < 0:
            raise ValueError("invalid work item")
        if len(set(item.dependencies)) != len(item.dependencies):
            raise ValueError("duplicate dependency")
        if item.name in item.dependencies or any(d not in by_name for d in item.dependencies):
            raise ValueError("self or missing dependency")

    indegree = {name: len(item.dependencies) for name, item in by_name.items()}
    followers = {name: [] for name in by_name}
    for item in items:
        for dep in item.dependencies:
            followers[dep].append(item.name)
    ready = [name for name, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    topo = []
    while ready:
        name = heapq.heappop(ready)
        topo.append(name)
        for child in sorted(followers[name]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(topo) != len(items):
        raise ValueError("dependency cycle detected")

    worker_free = [0] * max_workers
    finish: dict[str, int] = {}
    result = []
    for name in topo:
        item = by_name[name]
        earliest = max((finish[d] for d in item.dependencies), default=0)
        worker = min(range(max_workers), key=lambda i: (worker_free[i], i))
        start = max(earliest, worker_free[worker])
        end = start + item.duration_ms
        worker_free[worker] = end
        finish[name] = end
        result.append(ScheduledItem(name, worker, start, end))
    return tuple(result)


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    quality_pass_rate: float
    p95_latency_ms: int
    normalized_cost_per_task: float


def select_model(candidates: tuple[ModelCandidate, ...], *,
                 min_quality: float, max_p95_latency_ms: int | None = None) -> ModelCandidate:
    """Select the cheapest measured candidate that clears the quality/latency bar."""
    if not 0 <= min_quality <= 1 or not candidates:
        raise ValueError("invalid quality threshold or empty candidate set")
    valid = []
    for item in candidates:
        if (not item.model_id or not 0 <= item.quality_pass_rate <= 1
                or item.p95_latency_ms < 0 or item.normalized_cost_per_task < 0):
            raise ValueError("invalid candidate measurement")
        if item.quality_pass_rate < min_quality:
            continue
        if max_p95_latency_ms is not None and item.p95_latency_ms > max_p95_latency_ms:
            continue
        valid.append(item)
    if not valid:
        raise LookupError("no candidate satisfies the measured acceptance constraints")
    return min(valid, key=lambda x: (x.normalized_cost_per_task,
                                     x.p95_latency_ms, x.model_id))


def makespan(plan: tuple[ScheduledItem, ...]) -> int:
    return max((item.end_ms for item in plan), default=0)


if __name__ == "__main__":
    work = (
        WorkItem("read_a", 800),
        WorkItem("read_b", 600),
        WorkItem("analyze", 400, ("read_a", "read_b")),
        WorkItem("write_report", 200, ("analyze",)),
    )
    for item in schedule(work, max_workers=2):
        print(item)
