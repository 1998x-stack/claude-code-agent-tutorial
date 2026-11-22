#!/usr/bin/env python3
"""Browser acceptance for the course portal and currently refined chapters.

Requires: pip install playwright && python -m playwright install chromium
Produces screenshot PNGs and report.json; skips are never silently "passed".
"""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["site/index.html"] + [f"site/chapters/{n:02d}.html" for n in range(1, 21)]
WIDTHS = (1440, 768, 390, 360)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def run(output: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install playwright and chromium before browser QA") from exc

    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    failures = []
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for path in PAGES:
                    slug = "index" if path.endswith("index.html") else Path(path).stem
                    for width in WIDTHS:
                        page = browser.new_page(
                            viewport={"width": width, "height": 900},
                            device_scale_factor=1,
                            reduced_motion="reduce",
                        )
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.on("console", lambda msg: errors.append(
                            msg.text if msg.type == "error" else ""
                        ) if msg.type == "error" else None)
                        response = page.goto(f"{origin}/{path}", wait_until="networkidle")
                        page.locator("h1").first.wait_for(state="visible")
                        layout = page.evaluate("""() => ({
                            docWidth: document.documentElement.scrollWidth,
                            viewport: window.innerWidth,
                            h1s: document.querySelectorAll('h1').length,
                            brokenImages: [...document.images]
                                .filter(img => !img.complete || img.naturalWidth === 0)
                                .map(img => img.src),
                            headings: document.querySelectorAll('article h2').length
                        })""")
                        if response is None or response.status != 200:
                            errors.append(f"HTTP response was not 200: {response}")
                        if layout["docWidth"] > layout["viewport"] + 1:
                            errors.append(
                                f"horizontal overflow {layout['docWidth']} > {layout['viewport']}"
                            )
                        if layout["h1s"] != 1:
                            errors.append(f"expected 1 H1, saw {layout['h1s']}")
                        if layout["brokenImages"]:
                            errors.append(f"broken images: {layout['brokenImages']}")
                        if slug != "index" and layout["headings"] < 5:
                            errors.append("too few independent article sections")
                        if slug == "index" and width == 1440:
                            page.locator("[data-filter='base']").click()
                            visible = page.locator(".chapter:not([hidden])").count()
                            if visible != 5:
                                errors.append(f"base filter expected 5, got {visible}")
                            page.locator("[data-filter='all']").click()
                            page.locator("#chapter-search").fill("Tool Use")
                            visible = page.locator(".chapter:not([hidden])").count()
                            if visible < 1:
                                errors.append("chapter search did not return Tool Use")
                            page.locator("#chapter-search").fill("")
                        if width in (1440, 390):
                            page.screenshot(
                                path=str(output / f"{slug}-{width}.png"),
                                full_page=True, animations="disabled",
                            )
                        result = {
                            "page": path, "width": width,
                            "docWidth": layout["docWidth"],
                            "brokenImages": layout["brokenImages"],
                            "errors": [err for err in errors if err],
                        }
                        checks.append(result)
                        if result["errors"]:
                            failures.append(result)
                        page.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()

    (output / "report.json").write_text(json.dumps({
        "views_checked": len(checks),
        "pages_checked": len(PAGES),
        "widths": list(WIDTHS),
        "failures": failures,
        "checks": checks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Browser QA: {len(checks)} views, {len(failures)} failures")
    for failure in failures:
        print(f"FAIL {failure['page']} @ {failure['width']}: {failure['errors']}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("qa-output"))
    args = parser.parse_args()
    raise SystemExit(run(args.output))
