#!/usr/bin/env python3
"""Browser acceptance for all course pages at desktop, tablet and phone widths.

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
PAGES = ["site/index.html"] + [f"site/chapters/{n:02d}.html" for n in range(1, 29)]
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
                        page.on("console", lambda msg: errors.append(msg.text)
                                if msg.type == "error" else None)
                        page.on("response", lambda response: errors.append(
                            f"HTTP {response.status}: {response.url}"
                        ) if response.status >= 400 and response.url.startswith(origin) else None)
                        response = page.goto(f"{origin}/{path}", wait_until="networkidle")
                        page.locator("h1").first.wait_for(state="visible")

                        # Trigger lazy image requests and wait for decode before testing width.
                        page.evaluate("""async () => {
                            const images = [...document.images];
                            images.forEach(img => { img.loading = 'eager'; });
                            await Promise.all(images.map(img => img.decode().catch(() => null)));
                        }""")
                        layout = page.evaluate("""() => {
                            const localAnchors = [...document.querySelectorAll('a[href]')]
                                .map(a => new URL(a.href, location.href))
                                .filter(u => u.origin === location.origin && u.hash)
                                .filter(u => !document.getElementById(decodeURIComponent(u.hash.slice(1))))
                                .map(u => u.href);
                            return {
                                docWidth: document.documentElement.scrollWidth,
                                viewport: window.innerWidth,
                                h1s: document.querySelectorAll('h1').length,
                                mainCount: document.querySelectorAll('main').length,
                                brokenImages: [...document.images]
                                    .filter(img => !img.complete || img.naturalWidth === 0)
                                    .map(img => img.src),
                                headings: document.querySelectorAll('article h2').length,
                                figuresWithoutCaptions: [...document.querySelectorAll('figure')]
                                    .filter(fig => !fig.querySelector('figcaption')).length,
                                localAnchors
                            };
                        }""")
                        if response is None or response.status != 200:
                            errors.append(f"HTTP response was not 200: {response}")
                        if layout["docWidth"] > layout["viewport"] + 1:
                            errors.append(f"horizontal overflow {layout['docWidth']} > {layout['viewport']}")
                        if layout["h1s"] != 1:
                            errors.append(f"expected 1 H1, saw {layout['h1s']}")
                        if layout["mainCount"] != 1:
                            errors.append(f"expected one main landmark, saw {layout['mainCount']}")
                        if layout["brokenImages"]:
                            errors.append(f"broken images: {layout['brokenImages']}")
                        if layout["localAnchors"]:
                            errors.append(f"broken same-page anchors: {layout['localAnchors']}")
                        if layout["figuresWithoutCaptions"]:
                            errors.append(f"figures without captions: {layout['figuresWithoutCaptions']}")
                        if slug != "index":
                            if layout["headings"] < 5:
                                errors.append("too few independent article sections")
                            if page.locator("nav.lesson-nav a").count() < 5:
                                errors.append("chapter table of contents is missing or too short")

                        # The skip link must be the first keyboard stop.
                        page.keyboard.press("Tab")
                        if page.locator(".skip").count() and not page.evaluate(
                            "() => document.activeElement?.classList.contains('skip')"
                        ):
                            errors.append("skip link is not the first keyboard focus target")

                        # Exercise TOC navigation on every chapter at desktop width.
                        if slug != "index" and width == 1440:
                            first_toc = page.locator("nav.lesson-nav a").first
                            href = first_toc.get_attribute("href")
                            first_toc.click()
                            if href and page.evaluate("() => location.hash") != href:
                                errors.append(f"TOC click did not navigate to {href}")

                        if slug == "index" and width == 1440:
                            expected = {"base": 5, "tools": 6, "scale": 10, "advanced": 7}
                            for category, count in expected.items():
                                page.locator(f"[data-filter='{category}']").click()
                                visible = page.locator(".chapter:not([hidden])").count()
                                if visible != count:
                                    errors.append(f"{category} filter expected {count}, got {visible}")
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
