#!/usr/bin/env python3
"""Playwright headless verification: rendering at 3 widths, subresource
integrity, the mobile disclosure interaction, JS-disabled core content, and a
console-error gate.

Local by default. Pass --base-url https://thegrove.media/ to run the same
assertions against the live origin (feedback_curl_is_not_browser_verification.md
- a 200 from curl proves the edge is up, not that the page renders).

The console-error gate runs LOCAL ONLY: Cloudflare injects its Web Analytics
beacon at the edge, which errors in egress-restricted browsers and would make
the remote run flap (feedback_cf_edge_beacon_console_gate.md).

Serve host defaults to loopback. Set SERVE_HOST=10.9.5.10 when Chris needs to
open the served page from another machine (feedback_serve_urls_use_lan_ip.md).
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("SERVE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SERVE_PORT", "8095"))

VIEWPORTS = [("phone", 375, 812), ("tablet", 800, 1024), ("desktop", 1280, 900)]

# The Latest Episodes assertions below follow channels.json rather than being
# deleted while the section is off, so flipping latestEpisodesEnabled back to
# true re-arms the widget checks with no edit here. Off, they assert the
# inverse - that nothing renders and nothing is fetched - which is the property
# worth pinning while the section is disabled.
LATEST_ENABLED = json.loads(
    (ROOT / "content" / "channels.json").read_text()).get("latestEpisodesEnabled", True)

# Evaluated per viewport by run_checks. Kept as a module constant so the
# quoting stays readable.
JS_STYLING = """() => {
  const cs = getComputedStyle(document.body);
  const show = document.querySelector('section.show');
  return {
    paper: getComputedStyle(document.documentElement)
             .getPropertyValue('--paper').trim(),
    showBg: show ? getComputedStyle(show).backgroundColor : null,
    painted: cs.backgroundColor !== 'rgba(0, 0, 0, 0)'
             || cs.backgroundImage !== 'none',
  };
}"""

failures = []


def pass_(label, ok, extra=""):
    print(f"{'PASS' if ok else 'FAIL'} {label}{(' :: ' + extra) if extra else ''}")
    if not ok:
        failures.append(label)


class ReusableServer(socketserver.TCPServer):
    # Without this, a re-run inside TIME_WAIT dies with 'Address already in use'
    # inside the daemon thread, where the traceback is easy to miss.
    allow_reuse_address = True


def serve():
    os.chdir(ROOT)
    with ReusableServer((HOST, PORT), http.server.SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()


def run_checks(base, remote, shot_dir):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for name, w, h in VIEWPORTS:
            page = browser.new_page(viewport={"width": w, "height": h})
            console_errors, bad_responses = [], []
            page.on("console",
                    lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("response",
                    lambda r: bad_responses.append(f"{r.status} {r.url}")
                    if r.status >= 400 else None)
            # Proves the disabled section costs no network call. The route mock
            # below would happily answer a stray fetch, so counting requests is
            # the only way to tell "not fetched" from "fetched and mocked".
            episode_requests = []
            page.on("request",
                    lambda r: episode_requests.append(r.url) if "episodes?show=" in r.url else None)

            # Mock the-quill's episodeApi endpoint. This must be registered
            # BEFORE navigation - assets/latest-episodes.js fires its fetch
            # as soon as the deferred script runs on load, and a route added
            # after goto() would miss that first (only) request.
            page.route("**/episodes?show=quill*", lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps([
                    {"video_id": "abc123", "title": "The Forgotten Battle"},
                    {"video_id": "def456", "title": "Five Days at Fromelles"},
                ])))

            page.goto(base, wait_until="networkidle")
            page.mouse.wheel(0, 20000)          # trigger loading="lazy" images
            page.wait_for_timeout(700)

            pass_(f"{name}: page loads", page.title() == "TheGrove Studio")
            pass_(f"{name}: three shows in DOM", page.locator("section.show").count() == 3)
            pass_(f"{name}: every subresource 2xx/3xx",
                  not bad_responses, "; ".join(bad_responses[:5]))
            pass_(f"{name}: no 'Verified Aug' text", "Verified Aug" not in page.content())
            pass_(f"{name}: Sash link is buildwithsash.com",
                  page.locator('a[href="https://buildwithsash.com"]').count() == 1)
            pass_(f"{name}: canonical points at apex",
                  page.locator('link[rel="canonical"][href="https://thegrove.media/"]')
                      .count() == 1)

            if LATEST_ENABLED:
                widget_items = page.locator('[data-episode-api] li').count()
                pass_(f"{name}: latest-episodes widget renders fetched titles",
                      widget_items == 2, f"found {widget_items} items, expected 2")
            else:
                containers = page.locator('[data-episode-api]').count()
                scripts = page.locator('script').count()
                pass_(f"{name}: latest-episodes fully absent while disabled",
                      containers == 0 and scripts == 0,
                      f"containers={containers}, script tags={scripts}")
                pass_(f"{name}: no episode fetch while disabled",
                      not episode_requests, str(episode_requests))

            if not remote:
                pass_(f"{name}: zero console errors",
                      len(console_errors) == 0, str(console_errors))

            # Stylesheets actually PARSED - a 200 on the CSS is not proof of that.
            #
            # CORRECTED 2026-08-04 at Task 10, raised by the Task 10 implementer.
            # An earlier revision asserted getComputedStyle(document.body)
            # .backgroundColor was not the default. That is wrong at phone width:
            # below 768px body carries a gradient-only `background` shorthand (the
            # intentional "wall" texture), which sets background-IMAGE and leaves
            # background-COLOR as rgba(0,0,0,0). Measured: phone
            # bodyBg=rgba(0,0,0,0) bodyImg=radial-gradient(...); tablet and desktop
            # bodyBg=rgb(239,227,204) bodyImg=none. The implementer correctly
            # reported it as a bad assertion rather than loosening it or editing
            # the CSS.
            #
            # These three hold at every width and prove more than the original did:
            # the token sheet parsed, the site sheet parsed AND is consuming the
            # per-show custom properties, and the body is painted by one mechanism
            # or the other.
            styling = page.evaluate(JS_STYLING)
            pass_(f"{name}: tokens.css parsed (--paper resolves)",
                  styling["paper"] == "#EFE3CC", styling["paper"])
            pass_(f"{name}: site.css parsed and consuming per-show --field",
                  styling["showBg"] == "rgb(37, 30, 25)", str(styling["showBg"]))
            pass_(f"{name}: body is painted", styling["painted"])

            # Every RENDERED <img> decoded to real pixels.
            #
            # The getClientRects() filter is load-bearing, not defensive noise.
            # At phone width the show panels are collapsed (display:none), and
            # Chrome does not fetch loading="lazy" images inside a display:none
            # subtree - so assets/sash-photo.jpg legitimately reports
            # naturalWidth === 0 there. Verified directly: an unfiltered check
            # reports 1 false failure at 375px and 0 at 1280px. Filtering to
            # images that actually have a box keeps the gate honest at every
            # width instead of only at desktop.
            broken = page.evaluate("""
                Array.from(document.images)
                     .filter(i => i.getClientRects().length > 0)
                     .filter(i => !i.complete || i.naturalWidth === 0)
                     .map(i => i.getAttribute('src'))
            """)
            pass_(f"{name}: all images decoded", not broken, str(broken))

            if name == "phone":
                # The whole mobile interaction model is the checkbox hack. A broken
                # for/id pairing passes every other assertion in this file.
                panel = page.locator("#the-quill .panel").first
                pass_("phone: panel collapsed before tap", not panel.is_visible())
                page.locator('label[for="disc-the-quill"]').first.click()
                page.wait_for_timeout(250)
                pass_("phone: panel expands on tap", panel.is_visible())
            else:
                pass_(f"{name}: panel open by default at >=768px",
                      page.locator("#the-quill .panel").first.is_visible())

            # Scroll back to the top BEFORE capturing. This is not cosmetic.
            #
            # body's backdrop is a `background-attachment: fixed` gradient. If the
            # page is left scrolled when Playwright takes a full_page screenshot,
            # Chromium's stitched capture drops that fixed layer entirely and the
            # image comes out on white - the masthead's cream wordmark then reads
            # as near-invisible cream-on-white and the shot looks like a broken
            # site. Isolated 2026-08-04 by bisection:
            #   scroll=no  full_page=yes -> top-left rgb(27,20,15)   correct
            #   scroll=yes full_page=yes -> top-left rgb(255,255,255) ARTIFACT
            #   scroll=yes full_page=no  -> top-left rgb(27,20,15)   correct
            # These screenshots are the durable evidence artifact a human reviews,
            # so a misleading one is worse than none.
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(350)

            shot_dir.mkdir(parents=True, exist_ok=True)
            tag = "live" if remote else "local"
            page.screenshot(path=str(shot_dir / f"{tag}-{name}.png"), full_page=True)
            page.close()

        # --- No-JS: disable JS entirely; core content must still be present ---
        context = browser.new_context(java_script_enabled=False,
                                      viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(base, wait_until="load")
        pass_("no-JS: three show sections present",
              page.locator("section.show").count() == 3)
        pass_("no-JS: youtube links present",
              page.locator('a[href*="youtube.com"]').count() >= 3)
        pass_("no-JS: about links present",
              page.locator('a[href="https://shanku.net"]').count() == 1)

        # RULING-1 (Chris, 2026-08-10): the brief's Step 3 called for a
        # hardcoded `True` here ("widget absent with JS disabled - true by
        # construction since <script defer> never runs"). That can never
        # fail, so it verifies nothing. Replaced with a real DOM assertion
        # that documents the same intentional gap: with JS off, the-quill's
        # episodeApi container still renders (render.py emits it
        # unconditionally when episodeApi is set - see render_show) but stays
        # empty because assets/latest-episodes.js never executes to fill it.
        # A future reader should read this as "the widget's no-JS behavior is
        # an empty, still-present slot, not a missing one" - and this
        # assertion actually fails if that stops being true.
        # While latestEpisodesEnabled is false there is no container and no
        # script at all, so the no-JS story collapses into the JS story: the
        # page is identical either way. That is a stronger property than the
        # empty-slot behaviour it replaces, so assert it directly.
        widget = page.locator('[data-episode-api]')
        widget_li_count = widget.locator("li").count()
        if LATEST_ENABLED:
            pass_("no-JS: latest-episodes container present but empty with JS disabled (expected)",
                  widget.count() == 1 and widget_li_count == 0,
                  f"container count={widget.count()}, items={widget_li_count}")
        else:
            pass_("no-JS: page is identical with JS disabled (no widget to degrade)",
                  widget.count() == 0 and page.locator("script").count() == 0,
                  f"container count={widget.count()}, script tags={page.locator('script').count()}")

        context.close()
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None,
                    help="verify a remote origin instead of a local serve")
    ap.add_argument("--shot-dir", default=None)
    args = ap.parse_args()

    remote = args.base_url is not None
    if remote:
        base = args.base_url
    else:
        threading.Thread(target=serve, daemon=True).start()
        time.sleep(0.6)
        base = f"http://{HOST}:{PORT}/"

    default_shots = (
        "/Users/trunk/TheGrove/domains/site/thegrove-media/v1.1.0/verification"
    )
    shot_dir = Path(args.shot_dir or default_shots)

    print(f"verifying {base}  (mode: {'REMOTE' if remote else 'LOCAL'})\n")
    run_checks(base, remote, shot_dir)

    print(f"\n{'ALL PASS' if not failures else str(len(failures)) + ' FAILURES'}: "
          f"{', '.join(failures) if failures else ''}")
    print(f"screenshots -> {shot_dir}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
