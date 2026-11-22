"""Bounded concurrent *mock* subagent scheduling, no model execution.

Thread workers are NOT security sandboxes. The orchestration contract
documents inputs and returns results in submission order, even if completion
order differs. Workers used in tutorials must have no side effects.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Callable

from delegation_contract import Delegation, Finding, validate_result


@dataclass(frozen=True)
class Outcome:
    agent: str
    status: str
    report: Finding | None
    reason: str = ""


def run_batch(
    jobs: tuple[Delegation, ...],
    worker: Callable[[Delegation], Finding],
    *, max_workers: int = 2,
) -> tuple[Outcome, ...]:
    if not 1 <= max_workers <= 4:
        raise ValueError("concurrency limit must be between 1 and 4")
    if not jobs or len(jobs) > 8:
        raise ValueError("batch requires 1 to 8 jobs")
    if len({job.name for job in jobs}) != len(jobs):
        raise ValueError("duplicate agent name")
    if any(not job.goal.strip() or job.max_turns <= 0 for job in jobs):
        raise ValueError("invalid job")
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures: list[Future[Finding]] = [pool.submit(worker, job) for job in jobs]
        results: list[Outcome] = []
        # Input order is stable, independently of thread completion order.
        for job, future in zip(jobs, futures):
            try:
                report = future.result()
                validate_result(job, report)
            except Exception as exc:
                results.append(Outcome(job.name, "error", None, type(exc).__name__))
            else:
                results.append(Outcome(job.name, "ok", report))
    return tuple(results)
