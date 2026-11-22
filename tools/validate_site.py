#!/usr/bin/env python3
"""Offline structural, local-link, course-metadata and standalone-SVG checks."""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ERRORS: list[str] = []
DOCS: dict[Path, "Doc"] = {}


def error(message: str) -> None:
    ERRORS.append(message)


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.h1 = 0
        self.h2 = 0
        self.ids: set[str] = set()
        self.h2_without_id = 0

    def handle_starttag(self, tag, pairs):
        names = [key for key, _ in pairs]
        if len(names) != len(set(names)):
            error(f"duplicate HTML attribute in <{tag}>")
        attrs = dict(pairs)
        if tag == "h1":
            self.h1 += 1
        if tag == "h2":
            self.h2 += 1
            if not attrs.get("id"):
                self.h2_without_id += 1
        if attrs.get("id"):
            if attrs["id"] in self.ids:
                error("duplicate HTML id " + attrs["id"])
            self.ids.add(attrs["id"])
        for field in ("href", "src"):
            if attrs.get(field) is not None:
                self.links.append((field, attrs[field]))
        if tag == "img" and "alt" not in attrs:
            error("image missing alt attribute")

    def handle_startendtag(self, tag, pairs):
        self.handle_starttag(tag, pairs)


def parse_doc(file: Path) -> Doc:
    if file not in DOCS:
        obj = Doc()
        try:
            obj.feed(file.read_text(encoding="utf-8"))
            obj.close()
        except (OSError, UnicodeError) as exc:
            error(f"{file}: cannot read UTF-8 HTML: {exc}")
        DOCS[file] = obj
    return DOCS[file]


pages = sorted(SITE.rglob("*.html"))
for file in pages:
    obj = parse_doc(file)
    canonical = (
        file == SITE / "index.html" or
        (file.parent == SITE / "chapters" and file.stem.isdigit()
         and 1 <= int(file.stem) <= 28)
    )
    if canonical:
        if obj.h1 != 1:
            error(f"{file}: expected exactly one H1, found {obj.h1}")
        if file != SITE / "index.html" and obj.h2 < 5:
            error(f"{file}: expected at least five independent H2 sections, found {obj.h2}")
        if file != SITE / "index.html" and obj.h2_without_id:
            error(f"{file}: {obj.h2_without_id} H2 headings lack stable IDs")

for file in pages:
    obj = parse_doc(file)
    for field, link in obj.links:
        ref = urlparse(link)
        if ref.scheme == "javascript":
            error(f"{file}: javascript: URL is forbidden")
            continue
        if ref.scheme in {"mailto", "tel"} or ref.netloc or ref.scheme:
            continue
        if ref.scheme == "" and link.startswith("data:"):
            if field == "src":
                continue
            error(f"{file}: data: URL is not valid for href")
            continue
        if ref.path.startswith("/"):
            dest = (SITE / unquote(ref.path.lstrip("/"))).resolve()
        elif ref.path:
            dest = (file.parent / unquote(ref.path)).resolve()
        else:
            dest = file.resolve()
        if dest != SITE and SITE not in dest.parents:
            error(f"{file}: local link escapes site root: {link}")
            continue
        if dest.is_dir():
            dest = dest / "index.html"
        if not dest.exists():
            error(f"{file}: missing local {field}: {link}")
            continue
        fragment = unquote(ref.fragment)
        if fragment and dest.suffix.lower() == ".html":
            target_doc = parse_doc(dest)
            if fragment not in target_doc.ids:
                error(f"{file}: missing fragment target {fragment!r} in {dest}")

# The course manifest is a second source of truth; fail if it drifts from files.
manifest_path = SITE / "courses.json"
try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chapters = manifest.get("chapters")
    if manifest.get("chapterCount") != 28 or not isinstance(chapters, list) or len(chapters) != 28:
        error("courses.json must declare exactly 28 chapters")
    else:
        expected_nums = [f"{n:02}" for n in range(1, 29)]
        actual_nums = [item.get("num") for item in chapters]
        if actual_nums != expected_nums:
            error("courses.json chapter numbers must be the ordered sequence 01–28")
        for item in chapters:
            rel = item.get("file")
            if not isinstance(rel, str) or not (SITE / rel).is_file():
                error(f"courses.json references missing chapter: {rel!r}")
        if manifest.get("refinedChapters") != 28 or manifest.get("legacyPendingReview") != 0:
            error("course refinement metadata is inconsistent with 28 completed chapters")
except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
    error(f"courses.json is invalid: {exc}")

# Every SVG is a standalone, accessible XML document with closed local references.
svgs = sorted(SITE.rglob("*.svg"))
for file in svgs:
    try:
        root = ET.parse(file).getroot()
        if root.tag != "{http://www.w3.org/2000/svg}svg":
            error(f"{file}: root element must be SVG in the SVG namespace")
        if not root.get("viewBox"):
            error(f"{file}: missing viewBox")
        title = root.find("{http://www.w3.org/2000/svg}title")
        desc = root.find("{http://www.w3.org/2000/svg}desc")
        if title is None or not (title.text or "").strip():
            error(f"{file}: missing nonempty title")
        if desc is None or not (desc.text or "").strip():
            error(f"{file}: missing nonempty desc")
        ids: set[str] = set()
        references: list[str] = []
        for node in root.iter():
            ident = node.get("id")
            if ident:
                if ident in ids:
                    error(f"{file}: duplicate SVG id {ident}")
                ids.add(ident)
            for key, value in node.attrib.items():
                if key.endswith("}href") or key == "href":
                    if value.startswith("#"):
                        references.append(value[1:])
                references.extend(re.findall(r"url\(#([^)]+)\)", value))
        for ident in references:
            if ident not in ids:
                error(f"{file}: dangling SVG reference #{ident}")
    except (ET.ParseError, OSError) as exc:
        error(f"{file}: SVG XML error {exc}")

if ERRORS:
    print("\n".join("ERROR " + item for item in ERRORS))
    sys.exit(1)

print(f"PASS: {len(pages)} HTML pages, {len(svgs)} SVGs, 28 canonical chapters, "
      "local files/fragments, course manifest and SVG references")
