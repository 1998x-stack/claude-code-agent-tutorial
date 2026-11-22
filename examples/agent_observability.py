"""Privacy-first local event ledger for an agent runtime teaching harness.

This is not an OpenTelemetry SDK. It demonstrates correlation, low-risk
attributes, token categories, and the distinction between tool decisions
and completed tool results. Raw prompts, arguments, results and secrets are
never stored by this recorder.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import math
import re
from typing import Any


SCHEMAS: dict[str, dict[str, type | tuple[type, ...]]] = {
    "api.request": {
        "request_id": str, "model": str, "query_source": str,
        "input_tokens": int, "output_tokens": int,
        "cache_read_tokens": int, "cache_creation_tokens": int,
        "duration_ms": int, "success": bool,
    },
    "tool.decision": {
        "tool_use_id": str, "tool_name": str,
        "decision": str, "decision_source": str,
    },
    "tool.result": {
        "tool_use_id": str, "request_id": str, "tool_name": str,
        "success": bool, "duration_ms": int, "error_type": str,
        "input_bytes": int, "result_bytes": int,
    },
    "hook.result": {
        "hook_name": str, "success": bool, "duration_ms": int,
        "error_type": str,
    },
    "session.compaction": {
        "before_tokens": int, "after_tokens": int,
    },
}
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")


@dataclass(frozen=True)
class Event:
    sequence: int
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    timestamp_ms: int
    attributes: dict[str, Any]


class TraceRecorder:
    def __init__(self):
        self._events: list[Event] = []
        self._span_ids: set[tuple[str, str]] = set()

    @staticmethod
    def _check_int(value: Any, key: str) -> None:
        if type(value) is not int or value < 0:
            raise ValueError(f"{key} must be a nonnegative integer")

    def record(self, *, trace_id: str, span_id: str, name: str,
               timestamp_ms: int, attributes: dict[str, Any],
               parent_span_id: str | None = None) -> Event:
        if not SAFE_ID.fullmatch(trace_id) or not SAFE_ID.fullmatch(span_id):
            raise ValueError("trace_id and span_id must be bounded identifiers")
        if parent_span_id is not None and not SAFE_ID.fullmatch(parent_span_id):
            raise ValueError("invalid parent span ID")
        if type(timestamp_ms) is not int or timestamp_ms < 0:
            raise ValueError("timestamp_ms must be nonnegative")
        if name not in SCHEMAS or not isinstance(attributes, dict):
            raise ValueError("unknown event or malformed attributes")
        key = (trace_id, span_id)
        if key in self._span_ids:
            raise ValueError("span IDs must be unique within a trace")
        schema = SCHEMAS[name]
        clean: dict[str, Any] = {}
        # Strict allowlist: prompt text, tool arguments, tool results, paths,
        # headers and arbitrary user strings are intentionally not accepted.
        for field, value in attributes.items():
            expected = schema.get(field)
            if expected is None:
                continue
            if not isinstance(value, expected) or (expected is int and type(value) is not int):
                raise ValueError(f"invalid type for {field}")
            if expected is int:
                self._check_int(value, field)
            if expected is str and (not value or len(value) > 128):
                raise ValueError(f"{field} must be a short nonempty label")
            clean[field] = value
        required = {
            "api.request": {"model", "input_tokens", "output_tokens"},
            "tool.decision": {"tool_use_id", "tool_name", "decision"},
            "tool.result": {"tool_use_id", "tool_name", "success", "duration_ms"},
            "hook.result": {"hook_name", "success", "duration_ms"},
            "session.compaction": {"before_tokens", "after_tokens"},
        }[name]
        if not required.issubset(clean):
            raise ValueError(f"missing required fields: {sorted(required - clean.keys())}")
        if name == "tool.decision" and clean["decision"] not in {
            "accept", "reject", "ask", "allow"
        }:
            raise ValueError("unknown permission decision")
        if name == "session.compaction" and clean["after_tokens"] > clean["before_tokens"]:
            raise ValueError("compaction cannot increase the measured token count")
        event = Event(len(self._events) + 1, trace_id, span_id,
                      parent_span_id, name, timestamp_ms, clean)
        self._events.append(event)
        self._span_ids.add(key)
        return event

    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def summary(self) -> dict[str, Any]:
        token = {"input": 0, "cache_read": 0, "cache_creation": 0, "output": 0}
        tool = {"completed": 0, "failed": 0, "rejected": 0, "duration_ms": []}
        api_latencies: list[int] = []
        for event in self._events:
            a = event.attributes
            if event.name == "api.request":
                token["input"] += a.get("input_tokens", 0)
                token["cache_read"] += a.get("cache_read_tokens", 0)
                token["cache_creation"] += a.get("cache_creation_tokens", 0)
                token["output"] += a.get("output_tokens", 0)
                if "duration_ms" in a:
                    api_latencies.append(a["duration_ms"])
            elif event.name == "tool.result":
                tool["completed"] += 1
                tool["failed"] += int(not a["success"])
                tool["duration_ms"].append(a["duration_ms"])
            elif event.name == "tool.decision" and a["decision"] == "reject":
                tool["rejected"] += 1
        tool_durations = sorted(tool["duration_ms"])
        tool["p95_duration_ms"] = (
            tool_durations[max(0, math.ceil(.95 * len(tool_durations)) - 1)]
            if tool_durations else None
        )
        tool.pop("duration_ms")
        return {
            "token_counts": token,
            "input_total_including_cache": token["input"] + token["cache_read"] + token["cache_creation"],
            "api_p95_duration_ms": self._p95(api_latencies),
            "tools": tool,
            "event_count": len(self._events),
        }

    @staticmethod
    def _p95(values: list[int]) -> int | None:
        if not values:
            return None
        ordered = sorted(values)
        return ordered[max(0, math.ceil(.95 * len(ordered)) - 1)]

    def to_jsonl(self) -> str:
        return "".join(json.dumps(asdict(e), ensure_ascii=False, sort_keys=True) + "\n"
                       for e in self._events)


if __name__ == "__main__":
    trace = TraceRecorder()
    trace.record(trace_id="task-1", span_id="req-1", name="api.request",
                 timestamp_ms=10, attributes={
                     "request_id": "req-1", "model": "model-alias",
                     "input_tokens": 1000, "cache_read_tokens": 500,
                     "cache_creation_tokens": 0, "output_tokens": 120,
                     "duration_ms": 820, "success": True,
                 })
    trace.record(trace_id="task-1", span_id="tool-1", parent_span_id="req-1",
                 name="tool.result", timestamp_ms=30, attributes={
                     "request_id": "req-1", "tool_use_id": "call-1",
                     "tool_name": "Read", "success": True,
                     "duration_ms": 12, "input_bytes": 32, "result_bytes": 4096,
                 })
    print(json.dumps(trace.summary(), indent=2))
