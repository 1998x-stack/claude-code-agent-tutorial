"""Read-only coding-agent harness for Claude Messages API and offline replay.

No shell tool. No model-authored filesystem writes. A ProposeEdit tool returns
a unified diff but NEVER applies it. The model's final answer is not proof
that a patch passed tests or that the user approved a change.

Live mode needs the 'anthropic' SDK, a valid API key, a model ID and an
explicit user-selected workspace. Offline demo mode requires only stdlib.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

try:
    from workspace_tools import Workspace, ToolError
except ModuleNotFoundError:
    from examples.workspace_tools import Workspace, ToolError

READ_LIMIT = 12_000
TOOLS = [
    {
        "name": "ReadFile",
        "description": "Read UTF-8 content of one safe relative workspace file.",
        "input_schema": {
            "type": "object", "properties": {"path": {"type": "string", "maxLength": 512}},
            "required": ["path"], "additionalProperties": False,
        },
    },
    {
        "name": "ProposeEdit",
        "description": "Preview a single, unique string replacement as a unified diff; never write.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "maxLength": 512},
                "old": {"type": "string", "minLength": 1, "maxLength": 2000},
                "new": {"type": "string", "maxLength": 2000},
            },
            "required": ["path", "old", "new"], "additionalProperties": False,
        },
    },
]
SYSTEM = (
    "You are a read-only code-review assistant. Work within the provided "
    "workspace. You may read safe text files and propose diffs, but have no "
    "write, Bash or execution tools. Cite files and distinguish a proposal "
    "from an applied patch. Never claim that you ran tests."
)


@dataclass(frozen=True)
class ToolOutcome:
    tool_use_id: str
    name: str
    result: str
    failed: bool


@dataclass(frozen=True)
class AgentRun:
    stop_reason: str
    model_answer: str
    turns: int
    outcomes: tuple[ToolOutcome, ...]
    # This contains model-visible file contents and diffs. Do not persist or
    # print it in production without a separate data-retention policy.
    history: tuple[dict[str, Any], ...]


class SafeCodingAgent:
    def __init__(self, client: Any, workspace: Workspace, model: str, max_turns: int = 6):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model ID must be nonempty text")
        if type(max_turns) is not int or not 1 <= max_turns <= 20:
            raise ValueError("turn budget must be an integer from 1 to 20")
        self.client, self.workspace, self.model, self.max_turns = (
            client, workspace, model, max_turns
        )

    @staticmethod
    def _validate_display_path(path: str) -> None:
        if not isinstance(path, str) or not path or len(path) > 512:
            raise ToolError("path must be nonempty bounded text")
        if any(ord(char) < 32 or ord(char) == 127 for char in path):
            raise ToolError("control characters are forbidden in paths")

    def execute(self, name: str, args: Any) -> tuple[str, bool]:
        """Convert rejected/failed tools to explicit tool_result errors."""
        if not isinstance(args, dict):
            return "Invalid tool input: expected JSON object", True
        try:
            if name == "ReadFile":
                if set(args) != {"path"}:
                    raise ToolError("ReadFile accepts only path")
                self._validate_display_path(args["path"])
                data = self.workspace.read(args["path"])
                if len(data.encode("utf-8")) > READ_LIMIT:
                    raise ToolError("file exceeds model-visible result byte budget")
                return data, False
            if name == "ProposeEdit":
                if set(args) != {"path", "old", "new"}:
                    raise ToolError("ProposeEdit accepts path, old and new only")
                path, old, new = args["path"], args["old"], args["new"]
                self._validate_display_path(path)
                if not isinstance(old, str) or not isinstance(new, str):
                    raise ToolError("replacement values must be text")
                if (not old or len(old.encode("utf-8")) > 2000 or
                        len(new.encode("utf-8")) > 2000):
                    raise ToolError("replacement text is empty or exceeds the byte limit")
                if old == new:
                    raise ToolError("replacement is a no-op")
                current = self.workspace.read(path)
                if current.count(old) != 1:
                    raise ToolError("old text must match exactly once")
                updated = current.replace(old, new, 1)
                diff = "".join(unified_diff(
                    current.splitlines(keepends=True), updated.splitlines(keepends=True),
                    fromfile=f"a/{path}", tofile=f"b/{path}",
                ))
                if len(diff.encode("utf-8")) > READ_LIMIT:
                    raise ToolError("proposed diff exceeds output byte budget")
                return "PROPOSAL ONLY — NOT APPLIED\n" + diff, False
            raise ToolError("unknown tool; no fallback execution")
        except (ToolError, ValueError, TypeError, OSError) as exc:
            return f"{type(exc).__name__}: {exc}", True

    def run(self, task: str) -> AgentRun:
        if not isinstance(task, str) or not task.strip() or len(task.encode("utf-8")) > 8000:
            raise ValueError("task must be nonempty text within the byte budget")
        history: list[dict[str, Any]] = [{"role": "user", "content": task}]
        outcomes: list[ToolOutcome] = []
        seen_ids: set[str] = set()
        for turn in range(1, self.max_turns + 1):
            reply = self.client.messages.create(
                model=self.model, max_tokens=1024, system=SYSTEM,
                messages=history, tools=TOOLS,
            )
            if not isinstance(reply.content, (list, tuple)):
                return AgentRun("malformed_response", "", turn, tuple(outcomes), tuple(history))
            block_types = [getattr(block, "type", None) for block in reply.content]
            if any(isinstance(t, str) and t in {"server_tool_use", "mcp_tool_use"}
                   for t in block_types):
                return AgentRun("unsupported_server_tool_block", "", turn,
                                tuple(outcomes), tuple(history))
            tool_calls = [b for b in reply.content if getattr(b, "type", None) == "tool_use"]
            ids = [getattr(b, "id", None) for b in tool_calls]
            if any(not isinstance(i, str) or not i for i in ids):
                return AgentRun("invalid_tool_id", "", turn, tuple(outcomes), tuple(history))
            if len(set(ids)) != len(ids) or set(ids) & seen_ids:
                return AgentRun("duplicate_tool_id", "", turn, tuple(outcomes), tuple(history))
            if any(not isinstance(getattr(b, "name", None), str) or
                   not isinstance(getattr(b, "input", None), dict) for b in tool_calls):
                return AgentRun("malformed_tool_block", "", turn, tuple(outcomes), tuple(history))
            if tool_calls and reply.stop_reason != "tool_use":
                return AgentRun("inconsistent_tool_use", "", turn, tuple(outcomes), tuple(history))
            try:
                assistant_blocks = [b.model_dump(exclude_none=True) for b in reply.content]
                if not all(isinstance(block, dict) for block in assistant_blocks):
                    raise TypeError("content blocks must serialize to objects")
            except (AttributeError, TypeError, ValueError):
                return AgentRun("malformed_response", "", turn, tuple(outcomes), tuple(history))
            history.append({"role": "assistant", "content": assistant_blocks})
            if reply.stop_reason == "tool_use":
                if not tool_calls:
                    return AgentRun("inconsistent_tool_use", "", turn, tuple(outcomes), tuple(history))
                seen_ids.update(ids)
                results = []
                for call in tool_calls:
                    answer, failed = self.execute(call.name, call.input)
                    outcomes.append(ToolOutcome(call.id, call.name, answer, failed))
                    results.append({
                        "type": "tool_result", "tool_use_id": call.id,
                        "content": answer, "is_error": failed,
                    })
                # All client results are adjacent to and follow their tool_use blocks.
                history.append({"role": "user", "content": results})
                continue
            if reply.stop_reason == "end_turn":
                answer = "\n".join(
                    str(b.text) for b in reply.content if getattr(b, "type", None) == "text"
                )
                return AgentRun("model_ended_not_verified", answer, turn,
                                tuple(outcomes), tuple(history))
            # This client-only sample deliberately halts on pause_turn (which
            # belongs to server-tool loops), truncation, refusal, or unknown states.
            return AgentRun(f"halt:{reply.stop_reason}", "", turn, tuple(outcomes), tuple(history))
        return AgentRun("turn_budget_exhausted", "", self.max_turns,
                        tuple(outcomes), tuple(history))


class DemoBlock:
    def __init__(self, type_: str, **kwargs):
        self.type = type_
        self.__dict__.update(kwargs)

    def model_dump(self, exclude_none=True):
        return {"type": self.type, **{k: v for k, v in self.__dict__.items() if k != "type"}}


class DemoReply:
    def __init__(self, reason, blocks):
        self.stop_reason, self.content = reason, blocks


class DemoMessages:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return DemoReply("tool_use", [DemoBlock(
                "tool_use", id="call-read", name="ReadFile", input={"path": "greeting.txt"},
            )])
        if self.calls == 2:
            return DemoReply("tool_use", [DemoBlock(
                "tool_use", id="call-propose", name="ProposeEdit",
                input={"path": "greeting.txt", "old": "Hello", "new": "Hello, world"},
            )])
        return DemoReply("end_turn", [DemoBlock(
            "text", text="Prepared an un-applied diff; tests and approval are still required."
        )])


class DemoClient:
    def __init__(self):
        self.messages = DemoMessages()


def offline_demo() -> AgentRun:
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "greeting.txt").write_text("Hello\n", encoding="utf-8")
        run = SafeCodingAgent(DemoClient(), Workspace(root), "offline-fixture").run(
            "Read greeting.txt and propose replacing Hello with Hello, world."
        )
        if (root / "greeting.txt").read_text(encoding="utf-8") != "Hello\n":
            raise RuntimeError("read-only demo unexpectedly modified its fixture")
        return run


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely preview proposed coding-agent changes")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("demo", help="offline deterministic replay in a temporary workspace")
    live = sub.add_parser("live", help="opt-in Anthropic Messages API with no write tools")
    live.add_argument("--workspace", type=Path, required=True)
    live.add_argument("--model", required=True)
    live.add_argument("--task", required=True)
    args = parser.parse_args()
    if args.mode == "demo":
        run = offline_demo()
    else:
        import anthropic  # optional, never imported in offline tests
        run = SafeCodingAgent(
            anthropic.Anthropic(), Workspace(args.workspace), args.model,
        ).run(args.task)
    print("Model status:", run.stop_reason)
    for item in run.outcomes:
        print(f"{item.name} ({item.tool_use_id}) error={item.failed}\n{item.result}")
    print("Model text:", run.model_answer)
    print("WARNING: No edits were applied; acceptance tests and authorization are not inferred.")


if __name__ == "__main__":
    main()
