"""Minimal safe tool-using agent: an arithmetic tool, not a shell.
Requires: pip install anthropic (only for live API mode).
Set ANTHROPIC_API_KEY and ANTHROPIC_MODEL via environment variables.
"""
from __future__ import annotations

import os
import sys
from typing import Any

TOOLS = [{
    "name": "add_numbers",
    "description": "Add two bounded integers. Has no filesystem or network side effects.",
    "input_schema": {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        "required": ["a", "b"],
        "additionalProperties": False,
    },
}]


def dispatch_tool(name: str, args: Any) -> tuple[str, bool]:
    """Return (tool result text, is_error), never run arbitrary instructions."""
    if name != "add_numbers":
        return f"Tool {name!r} is not registered", True
    if not isinstance(args, dict) or set(args) != {"a", "b"}:
        return "Expected exactly two arguments: a and b", True
    a, b = args["a"], args["b"]
    # bool subclasses int in Python, but is not a valid JSON integer here.
    if type(a) is not int or type(b) is not int:
        return "Arguments a and b must be integers", True
    if abs(a) > 10_000 or abs(b) > 10_000:
        return "Inputs must be between -10000 and 10000", True
    return str(a + b), False


def run_agent(client: Any, model: str, task: str, max_turns: int = 8) -> str:
    if not (1 <= max_turns <= 32):
        raise ValueError("max_turns must be between 1 and 32")
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system="You can use add_numbers to add integers. Do not invent tool outputs.",
            messages=messages,
            tools=TOOLS,
        )
        # Preserve *all* assistant blocks (text and every tool_use).
        assistant_blocks = [block.model_dump(exclude_none=True) for block in response.content]
        messages.append({"role": "assistant", "content": assistant_blocks})
        if response.stop_reason == "tool_use":
            calls = [block for block in response.content if block.type == "tool_use"]
            if not calls:
                raise RuntimeError("tool_use stop without tool_use blocks")
            results = []
            for call in calls:
                text, failed = dispatch_tool(call.name, call.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": text,
                    "is_error": failed,
                })
            # Each assistant tool_use must have a matching result in one
            # immediately following user message.
            messages.append({"role": "user", "content": results})
        elif response.stop_reason == "end_turn":
            return "\n".join(
                block.text for block in response.content
                if block.type == "text"
            )
        else:
            # e.g. max_tokens: an incomplete response is not success.
            raise RuntimeError(f"Agent stopped without final answer: {response.stop_reason}")
    raise RuntimeError(f"Agent hit maximum number of turns ({max_turns})")


def main() -> None:
    model = os.getenv("ANTHROPIC_MODEL")
    if not model:
        raise SystemExit("Set ANTHROPIC_MODEL to a model your account can use.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY in your shell; never commit it.")
    from anthropic import Anthropic
    task = " ".join(sys.argv[1:]) or "Please add 7 and 5 using the tool."
    print(run_agent(Anthropic(), model, task))


if __name__ == "__main__":
    main()
