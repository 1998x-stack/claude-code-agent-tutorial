"""Deterministic observable agent loop; a teaching engine, not Claude Code code.

The generator yields *application events* after each completed model call.
It is NOT a network token-stream decoder. See the API Streaming documentation
for content_block_delta and partial tool-input semantics.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class Event:
    kind: str
    turn: int
    detail: str


def run_events(
    client: Any,
    model: str,
    task: str,
    tool_handler: Callable[[str, dict], tuple[str, bool]],
    *,
    max_turns: int = 6,
    cancelled: Callable[[], bool] = lambda: False,
) -> Iterator[Event]:
    if not (1 <= max_turns <= 32):
        raise ValueError("invalid turn budget")
    history: list[dict[str, Any]] = [{"role": "user", "content": task}]
    for turn in range(1, max_turns + 1):
        if cancelled():
            yield Event("halt", turn, "cancelled")
            return
        yield Event("request", turn, "model request started")
        reply = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=history,
            tools=[{
                "name": "add_numbers",
                "description": "Add two integers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"}, "b": {"type": "integer"}
                    },
                    "required": ["a", "b"],
                },
            }],
        )
        history.append({
            "role": "assistant",
            "content": [b.model_dump(exclude_none=True) for b in reply.content],
        })
        if reply.stop_reason == "tool_use":
            calls = [b for b in reply.content if b.type == "tool_use"]
            if not calls:
                yield Event("halt", turn, "inconsistent tool_use response")
                return
            results = []
            for call in calls:
                try:
                    data, failed = tool_handler(call.name, call.input)
                except Exception as exc:  # translate failure into a matching result
                    data, failed = f"{type(exc).__name__}: tool failed", True
                results.append({
                    "type": "tool_result", "tool_use_id": call.id,
                    "content": str(data), "is_error": bool(failed),
                })
                yield Event("tool_result", turn, f"{call.id}: {'error' if failed else 'ok'}")
            history.append({"role": "user", "content": results})
        elif reply.stop_reason == "end_turn":
            answer = "\n".join(
                b.text for b in reply.content if b.type == "text"
            )
            yield Event("final", turn, answer)
            return
        else:
            yield Event("halt", turn, f"stop_reason={reply.stop_reason}")
            return
    yield Event("halt", max_turns, "turn budget exhausted")
