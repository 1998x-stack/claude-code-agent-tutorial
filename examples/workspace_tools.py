"""Educational workspace tools; NOT a production security sandbox.

There is deliberately no general shell execution. BashPreview accepts only
two fixed read-only operations implemented with Python. The tool names model
an interface, not the privileged tools built into Claude Code.
"""
from __future__ import annotations
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
from typing import Any

class ToolError(ValueError):
    """A safe, reportable tool rejection."""

MAX_TEXT = 16_384
FORBIDDEN = {".git", ".env", ".ssh", ".aws", ".claude", "__pycache__"}
FORBIDDEN_CASEFOLD = frozenset(name.casefold() for name in FORBIDDEN)


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ToolError("workspace must be a directory")

    def target(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative or len(relative) > 1024:
            raise ToolError("expected a nonempty bounded relative path")
        if any(ord(char) < 32 or ord(char) == 127 for char in relative):
            raise ToolError("control characters are forbidden in paths")
        if "\\" in relative or ":" in relative:
            raise ToolError("Windows separators, drives and alternate streams are forbidden")
        win_path = PureWindowsPath(relative)
        path = PurePosixPath(relative)
        if (path.is_absolute() or win_path.is_absolute() or win_path.drive or
                not path.parts or any(p in ("..", ".") for p in path.parts)):
            raise ToolError("path traversal or absolute path is forbidden")
        if any(p.casefold() in FORBIDDEN_CASEFOLD or p.casefold().startswith(".env.")
               for p in path.parts):
            raise ToolError("reserved or sensitive path")
        candidate = self.root.joinpath(*path.parts)
        current = self.root
        for component in path.parts:
            current = current / component
            if current.is_symlink():
                raise ToolError("symlinks are not supported")
        try:
            candidate.resolve(strict=False).relative_to(self.root)
        except ValueError as exc:
            raise ToolError("path escapes the workspace") from exc
        return candidate

    def bash_preview(self, command: str) -> str:
        """Emulate only 'pwd' and 'ls'. This never invokes a shell."""
        if command == "pwd":
            return str(self.root)
        if command == "ls":
            entries = sorted(
                p.name for p in self.root.iterdir()
                if not p.is_symlink() and p.name.casefold() not in FORBIDDEN_CASEFOLD
            )
            return "\n".join(entries)[:MAX_TEXT]
        raise ToolError("BashPreview supports only the exact commands 'pwd' or 'ls'")

    def read(self, path: str) -> str:
        file = self.target(path)
        if not file.is_file():
            raise ToolError("not a regular file")
        try:
            # Bound the actual read, not only a prior stat that can go stale.
            with file.open("rb") as stream:
                raw = stream.read(MAX_TEXT + 1)
            if len(raw) > MAX_TEXT:
                raise ToolError("file exceeds the demonstration byte limit")
            return raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ToolError("cannot read UTF-8 text") from exc

    def _atomic_write(self, file: Path, content: str) -> None:
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_TEXT:
            raise ToolError("content must be UTF-8 text within the size limit")
        if not file.parent.is_dir():
            raise ToolError("parent directory does not exist")
        # Staging and replace reduce partial writes, not filesystem race attacks.
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=file.parent, encoding="utf-8", delete=False
            ) as tmp:
                tmp_name = tmp.name
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, file)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def write(self, path: str, content: str, approved: bool = False) -> str:
        if approved is not True:
            raise ToolError("explicit approval required to create a file")
        file = self.target(path)
        if file.exists():
            raise ToolError("Write creates new files only; use Edit for changes")
        self._atomic_write(file, content)
        return f"created {path}"

    def edit(self, path: str, old: str, new: str, approved: bool = False) -> str:
        if approved is not True:
            raise ToolError("explicit approval required to change a file")
        if not isinstance(old, str) or not old or not isinstance(new, str):
            raise ToolError("old must be nonempty text, new must be text")
        file = self.target(path)
        current = self.read(path)
        if current.count(old) != 1:
            raise ToolError("Edit requires exactly one matching occurrence")
        updated = current.replace(old, new, 1)
        self._atomic_write(file, updated)
        return f"edited {path}"

    def dispatch(self, name: str, args: Any, approved: bool = False) -> tuple[str, bool]:
        """Return a tool_result-compatible (content, is_error) pair."""
        if not isinstance(name, str) or name not in {"BashPreview", "Read", "Write", "Edit"}:
            return "unregistered tool", True
        if not isinstance(args, dict):
            return "tool arguments must be an object", True
        expected = {
            "BashPreview": {"command"},
            "Read": {"path"},
            "Write": {"path", "content"},
            "Edit": {"path", "old", "new"},
        }[name]
        if set(args) != expected:
            return "unexpected or missing tool arguments", True
        try:
            if name == "BashPreview":
                return self.bash_preview(args["command"]), False
            if name == "Read":
                return self.read(args["path"]), False
            if name == "Write":
                return self.write(args["path"], args["content"], approved), False
            return self.edit(args["path"], args["old"], args["new"], approved), False
        except (ToolError, OSError, TypeError, UnicodeError) as exc:
            return f"{type(exc).__name__}: {exc}", True
