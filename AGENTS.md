# AGENTS.md — claude-code-agent-tutorial

## Mission
Build independently understandable, technically precise Chinese tutorials. The Pages release root is `site/`; each canonical chapter is `site/chapters/NN.html`.

## Source-of-truth boundary
- Every unusual claim must be tagged/clarified as **官方公开契约**, **可观察行为**, or **教学设计**.
- Never claim proprietary Claude Code internals, hidden layer counts, exact compression percentages, performance metrics, model-specific parameters or private function names as fact without inspectable evidence and version.
- Do not recommend unauthorized reverse engineering or license circumvention.
- Primary sources: https://code.claude.com/docs/en/overview and https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview.

## Article contract
Reader problem → simple baseline → detailed SVG → protocol or executable mechanism → error paths → exercise → references.
One H1, semantic H2, self-contained context, native TOC, previous/next and precise source links.
Standalone `site/assets/svg/*.svg`: xmlns, viewBox, title, desc, unique IDs, accessible labels and captions. SVG labels nominally >=13px; no decorative unexplained arrows.
Use `site/assets/css/article.css`. No external fonts/scripts/CDNs. Keep 360px/390px phone views and print legible.
No manufacturing/provenance prose in article body; do not copy figures or copy text from other sites.

## Code and security
No model-generated shell commands via `shell=True`, no default unrestricted file writes, no embedded API keys, no command execution during page load. Illustrate tool validation, rejected tool names, error results, bounded turns, human approvals for side effects.
Tutorial code is not production-safe unless explicitly engineered and tested so.

## Maintenance
Chapter slugs `01`–`28` are stable. New chapters 06–10 use guarded workspace tools, layered prompts, event state machines, dependency DAGs and checkpoint budgeting. Preserve root and site redirects for old URLs. Update `site/courses.json`, homepage and links when changing chapter titles.
Original chapters 01–10 archived at `archive/initial/`. Chapters 01–10 are refined; chapters 11–28 remain legacy and need technical review.
Run `python3 tools/validate_site.py`, offline unit tests, and browser checks at 1440/768/390/360 with JS errors, horizontal overflow, figures, keyboard focus and nav if tooling permits. Record skipped browser steps, do not invent QA status.
Publish `site/` using GitHub Pages Actions workflow; confirm deployment rather than assuming.
