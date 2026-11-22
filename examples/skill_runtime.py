"""Offline model of Claude Code skill discovery and invocation boundaries.

Supports only a documented, deliberately small frontmatter subset. It does
not execute skill instructions, grant tool permissions, run shell injection,
or spawn subagents. Use a real YAML parser and the product runtime in production.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

NAME = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
BOOLS = {"true": True, "yes": True, "on": True, "1": True,
         "false": False, "no": False, "off": False, "0": False}


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    disable_model_invocation: bool = False
    user_invocable: bool = True
    context: str | None = None
    agent: str | None = None
    background: bool = True
    allowed_tools: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillDocument:
    metadata: SkillMetadata
    body: str


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _bool(value: str, field: str) -> bool:
    result = BOOLS.get(_scalar(value).lower())
    if result is None:
        raise ValueError(f"{field} must be a YAML boolean")
    return result


def _list(value: str, rows: list[str]) -> tuple[str, ...]:
    if value.strip():
        v = value.strip()
        if v.startswith("[") and v.endswith("]"):
            return tuple(_scalar(x) for x in v[1:-1].split(",") if x.strip())
        return tuple(x for x in re.split(r"[\s,]+", _scalar(v)) if x)
    return tuple(rows)


def _parse_header(header: str, folder_name: str) -> SkillMetadata:
    values: dict[str, str] = {}
    lists: dict[str, list[str]] = {"allowed-tools": [], "paths": []}
    active_list: str | None = None
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and active_list in lists:
            lists[active_list].append(_scalar(stripped[2:]))
            continue
        key, colon, value = stripped.partition(":")
        if not colon:
            raise ValueError("unsupported frontmatter line")
        key, value = key.strip(), value.strip()
        active_list = key if key in lists and not value else None
        if key in {"name", "description", "disable-model-invocation",
                   "user-invocable", "context", "agent", "background",
                   "allowed-tools", "paths"}:
            values[key] = value
    name = _scalar(values.get("name", folder_name))
    description = _scalar(values.get("description", ""))
    if not NAME.fullmatch(name) or name != folder_name:
        raise ValueError("skill name must be kebab-case and match its directory")
    if not description:
        raise ValueError("description is required by this teaching catalog")
    context = _scalar(values["context"]) if values.get("context") else None
    if context not in {None, "fork"}:
        raise ValueError("context supports only the documented 'fork' value")
    agent = _scalar(values["agent"]) if values.get("agent") else None
    return SkillMetadata(
        name=name, description=description,
        disable_model_invocation=_bool(values.get("disable-model-invocation", "false"),
                                       "disable-model-invocation"),
        user_invocable=_bool(values.get("user-invocable", "true"), "user-invocable"),
        context=context, agent=agent,
        background=_bool(values.get("background", "true"), "background"),
        allowed_tools=_list(values.get("allowed-tools", ""), lists["allowed-tools"]),
        paths=_list(values.get("paths", ""), lists["paths"]),
    )


class SkillCatalog:
    def __init__(self, root: Path):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("skills root must be a directory")
        self.errors: list[str] = []

    def _directory(self, name: str) -> Path:
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("invalid skill name")
        folder = self.root / name
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("unknown skill or symlink directory")
        resolved = folder.resolve(strict=True)
        if resolved.parent != self.root:
            raise ValueError("skill directory escapes catalog root")
        return folder

    def _read(self, name: str) -> tuple[SkillMetadata, str]:
        folder = self._directory(name)
        path = folder / "SKILL.md"
        if path.is_symlink() or not path.is_file():
            raise ValueError("SKILL.md is missing or is a symlink")
        if path.stat().st_size > 64_000:
            raise ValueError("skill file exceeds teaching size limit")
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---\n"):
            raise ValueError("frontmatter must begin on the first line")
        header, sep, rest = raw[4:].partition("\n---\n")
        if not sep:
            raise ValueError("closing frontmatter delimiter is missing")
        return _parse_header(header, name), rest.strip()

    def discover(self) -> tuple[SkillMetadata, ...]:
        """Return metadata only; the skill body is not returned to the caller."""
        found = []
        self.errors.clear()
        for folder in sorted(self.root.iterdir()):
            if folder.is_symlink() or not folder.is_dir() or not NAME.fullmatch(folder.name):
                continue
            try:
                metadata, _ = self._read(folder.name)
                found.append(metadata)
            except (ValueError, UnicodeError, OSError) as exc:
                self.errors.append(f"{folder.name}: {exc}")
        return tuple(found)

    def can_invoke(self, name: str, caller: str) -> bool:
        metadata, _ = self._read(name)
        if caller == "user":
            return metadata.user_invocable
        if caller == "model":
            return not metadata.disable_model_invocation
        raise ValueError("caller must be 'user' or 'model'")

    def invoke(self, name: str, caller: str) -> SkillDocument:
        metadata, body = self._read(name)
        if not self.can_invoke(name, caller):
            raise PermissionError(f"{caller} invocation is disabled for {name}")
        return SkillDocument(metadata, body)

    def read_supporting_file(self, name: str, relative_path: str) -> str:
        """Read one referenced resource without permitting traversal or symlinks."""
        folder = self._directory(name)
        rel = Path(relative_path)
        if rel.is_absolute() or not relative_path or ".." in rel.parts:
            raise ValueError("supporting path must stay inside the skill directory")
        target = folder / rel
        if any(part.is_symlink() for part in [target, *target.parents]
               if part != folder):
            raise ValueError("symlinks are not followed by this demo")
        resolved = target.resolve(strict=True)
        if folder not in resolved.parents or not resolved.is_file():
            raise ValueError("supporting file escapes skill directory")
        if resolved.stat().st_size > 128_000:
            raise ValueError("supporting file too large for demo")
        return resolved.read_text(encoding="utf-8")


if __name__ == "__main__":
    import sys
    catalog = SkillCatalog(Path(sys.argv[1]))
    for skill in catalog.discover():
        print(f"/{skill.name}: {skill.description}")
    for error in catalog.errors:
        print("SKIPPED:", error)
