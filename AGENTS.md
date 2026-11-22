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
Original chapters 01–25 archived at `archive/initial/`. Chapters 01–25 are refined; chapters 26–28 remain legacy and need technical review.
Run `python3 tools/validate_site.py`, offline unit tests, and browser checks at 1440/768/390/360 with JS errors, horizontal overflow, figures, keyboard focus and nav if tooling permits. Record skipped browser steps, do not invent QA status.
Publish `site/` using GitHub Pages Actions workflow; confirm deployment rather than assuming.

## Skills and instructions, version scope
- The canonical cross-tool guide is AGENTS.md. CLAUDE.md imports it for Claude Code compatibility; do not create a second conflicting manual.
- AGENTS.md auto-loading is version- and configuration-dependent. Read https://code.claude.com/docs/en/memory before declaring it loaded automatically.
- Claude Code skill frontmatter `allowed-tools` can preapprove named tools during the invocation turn, subject to policy. The offline SkillCatalog may parse this field as metadata but must never turn it into real tool grants or execute skill body text.
- Subagent context isolation is not an OS sandbox. Authorization must be independently checked at execution time.
- Permission modes are version-sensitive; do not hardcode "seven modes" or assume auto/classifier is universally available.

## MCP 2026, sandbox, and context audits
- MCP 2026-07-28 is the modern request-metadata era. Modern requests include `params._meta` version and clientCapabilities; session-level `initialize` and notifications/initialized belong to <=2025-11-25. Never mix protocol envelopes or claim legacy handshake is universal.
- Trust no unverified tool annotations. Use host-assigned server namespaces, external tool authorization, JSON Schema validation, and explicit error/resultType handling.
- Modern MCP 2026 standard transports are stdio and Streamable HTTP; Claude Code product can support additional legacy SSE or WebSocket server options. State scope precisely.
- Bash sandbox is OS-enforced, not emulated by regex/string filtering. Teaching code must not execute arbitrary model shell commands. Document non-sandbox retry risks and true OS-level test requirements.
- Prompt caching does not decrease context-window occupancy. Record actual usage cache fields; no fixed prefix hit rates without reproducible evidence.
\n## Skills, Harness, Observability and Ecosystem
- Do not invent `triggers`, `priority`, automatic Evict heuristics or fixed skill-token budgets as official Claude Code Skills behavior. Use current official frontmatter and distinguish `disable-model-invocation` from `user-invocable`.
- Invoked Skill body can remain in conversation context; `allowed-tools` is turn-scoped. `context: fork` is a separate subagent context, not an OS sandbox.
- Completion must be evidence-based: required checks, artifacts, bounded steps, and human approval for side effects. Do not infer success from words like `done` or model stop markers alone.
- Observability should correlate `trace_id`, `span_id`, `request_id` and `tool_use_id`. Distinguish tool decisions from executed tool results; default to excluding raw prompts, tool arguments, results, secrets and source code.
- Performance claims require a pinned model/version, fixed task set, repeated measurements, quality threshold, P50/P95 latency and real usage/cost fields. Do not reuse fixed cache hit-rate or price claims.
- Plugin and MCP marketplace entries are not security guarantees. Review license, pinned version, hooks, scripts, binaries, MCP servers, network egress, data handling and update policy.
