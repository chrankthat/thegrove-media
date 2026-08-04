#!/usr/bin/env python3
"""Render scripts/og_image.html to assets/og-image.png at 1200x630 - the
standard OG/Twitter card size. Headless chromium launched directly, not via
Playwright MCP (feedback_playwright_mcp_headed_fails_over_ssh.md).

scripts/og_image.html is served publicly at thegrove.media/scripts/og_image.html
(Cloudflare Pages serves this repo's root with no build step) but contains no
secrets, so that is harmless."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "og_image.html"
OUT = ROOT / "assets" / "og-image.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
    page.goto(SRC.as_uri(), wait_until="networkidle")

    page.wait_for_timeout(500)
    loaded = page.evaluate("document.fonts.check(\"600 64px Spectral\")")
    if not loaded:
        raise SystemExit("Spectral webfont did not load - OG card would ship in "
                         "fallback typography. Re-run with network access.")

    page.screenshot(path=str(OUT))
    browser.close()

print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
