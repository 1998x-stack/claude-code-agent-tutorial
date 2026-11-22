"""A deterministic context-engineering experiment worksheet.

No real tokenizer, cache, SDK or pricing API. Tokens are measured/mock counts.
Caching and compaction are different: a cached token still occupies context.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class InputBreakdown:
    stable_system: int
    tool_definitions: int
    active_history: int
    stale_tool_results: int

    def total(self) -> int:
        parts = (self.stable_system, self.tool_definitions,
                 self.active_history, self.stale_tool_results)
        if any(type(x) is not int or x < 0 for x in parts):
            raise ValueError("token counts must be nonnegative integers")
        return sum(parts)


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

    def full_input(self) -> int:
        # API input_tokens normally excludes cache creation/read portions.
        parts = (self.input_tokens, self.cache_creation_input_tokens,
                 self.cache_read_input_tokens, self.output_tokens)
        if any(type(x) is not int or x < 0 for x in parts):
            raise ValueError("invalid token usage counters")
        return sum(parts[:3])

    def cache_read_fraction(self) -> float:
        total = self.full_input()
        return self.cache_read_input_tokens / total if total else 0.0


def simulate(baseline: InputBreakdown, *,
             deferred_schema_tokens: int = 0,
             removed_stale_result_tokens: int = 0,
             cached_prefix_tokens: int = 0) -> dict[str, int]:
    """Return count changes only; no invented latency, cost, or model quality."""
    initial = baseline.total()
    if (type(deferred_schema_tokens) is not int
            or not 0 <= deferred_schema_tokens <= baseline.tool_definitions):
        raise ValueError("invalid deferred schema amount")
    if (type(removed_stale_result_tokens) is not int
            or not 0 <= removed_stale_result_tokens <= baseline.stale_tool_results):
        raise ValueError("invalid clear amount")
    final = initial - deferred_schema_tokens - removed_stale_result_tokens
    if (type(cached_prefix_tokens) is not int
            or not 0 <= cached_prefix_tokens <= final):
        raise ValueError("cache amount cannot exceed resulting context")
    return {
        "baseline_input_tokens": initial,
        "optimized_input_tokens": final,
        "saved_context_tokens": initial - final,
        "cached_input_tokens": cached_prefix_tokens,
        "cached_context_savings": 0,
    }


def retain_critical(available_facts: set[str], protected: set[str]) -> None:
    """Fail closed if a proposed summary drops a critical task invariant."""
    if not protected.issubset(available_facts):
        raise ValueError("summary omits mandatory constraints or pending work")


if __name__ == "__main__":
    print(simulate(InputBreakdown(3000, 5000, 8000, 6000),
                   deferred_schema_tokens=3000,
                   removed_stale_result_tokens=4500,
                   cached_prefix_tokens=5000))
