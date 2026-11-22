"""Safe educational catalog of local SKILL.md files (no execution).

This parses a tiny subset of YAML-like frontmatter for demonstration only:
name and description string lines. Real Claude Code supports more formats,
frontmatter fields, scopes, dynamic context and permission interactions.
The catalog deliberately ignores allowed-tools and all executable commands.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

NAME = re.compile(r"^[a-z][a-z0-9-]{0,47}$")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str


class SkillCatalog:
    def __init__(self, root: Path):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("skills root must be a directory")

    def _skill_file(self, name: str) -> Path:
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("invalid skill name")
        folder = self.root / name
        file = folder / "SKILL.md"
        if folder.is_symlink() or file.is_symlink() or not file.is_file():
            raise ValueError("unknown skill or symlink")
        if file.stat().st_size > 32_768:
            raise ValueError("skill metadata too large for demo")
        return file

    def load(self, name: str) -> Skill:
        raw = self._skill_file(name).read_text(encoding="utf-8")
        if not raw.startswith("---\n"):
            raise ValueError("frontmatter required")
        _, sep, rest = raw.partition("---\n")
        header, closing, body = rest.partition("\n---\n")
        if not closing:
            raise ValueError("unclosed frontmatter")
        fields: dict[str, str] = {}
        for row in header.splitlines():
            key, colon, value = row.partition(":")
            if colon and key.strip() in {"name", "description"}:
                fields[key.strip()] = value.strip().strip('"').strip("'")
        if fields.get("name") != name or not fields.get("description"):
            raise ValueError("name mismatch or missing description")
        return Skill(name, fields["description"], body.strip())

    def descriptions(self) -> tuple[tuple[str, str], ...]:
        found = []
        for folder in sorted(self.root.iterdir()):
            if folder.is_dir() and not folder.is_symlink() and NAME.fullmatch(folder.name):
                try:
                    skill = self.load(folder.name)
                except (ValueError, UnicodeError, OSError):
                    continue
                found.append((skill.name, skill.description))
        return tuple(found)
