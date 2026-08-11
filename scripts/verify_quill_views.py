#!/usr/bin/env python3
"""Playwright headless verification for the Quill page's consolidated view counts.

The page shows a CROSS-PLATFORM total (`total_view_count`), not the YouTube-only
`view_count`, at all three count sites, and ranks Most Popular on it. This pins
that behaviour, the three platform marks that label the number, and the two
guards that were load-bearing before the change and must stay load-bearing after.

Every check runs against a mocked /episodes response, so the suite does not flap
when the nightly social-metrics job moves a real number. One opt-in check
(--live-api) hits the real endpoint to confirm the contract still carries
total_view_count - run it when you suspect the worker changed, not in a loop.

Local serve only. A 200 from curl proves the edge is up, not that the page
renders (feedback_curl_is_not_browser_verification.md). Set SERVE_HOST=10.9.5.10
to open the served page from another machine (feedback_serve_urls_use_lan_ip.md).
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("SERVE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SERVE_PORT", "8096"))
API_URL = "https://quill-scheduler.chris-ba5.workers.dev/episodes?show=quill"

# Fixture mirrors the real response shape. The ratios are the point: Toller is
# 429x its YouTube count and Albuera is 1.2x, so ranking on the wrong field
# visibly reorders the podium. Chapters has total == view_count, which is
# correct rather than a gap - that format has no shorts and no crossposts.
FIXTURE = [
    # slug,                    view, total, published
    ("tq01.3-battle-toller",      5, 2145, "2026-08-02T14:00:00+00:00"),
    ("tq01.2-battle-sakurai",    17, 1879, "2026-07-26T14:00:00+00:00"),
    ("007-battle-rabe",          26, 1634, "2026-07-19T14:00:00+00:00"),
    ("002-battle-fromelles",    376, 1363, "2026-06-14T14:00:00+00:00"),
    ("003-battle-albuera",      839,  977, "2026-06-21T14:00:00+00:00"),
    ("tq02.1-battle-nakamura",   13,  905, "2026-08-09T14:00:00+00:00"),
    ("005-chapters-three-rules", 23,   23, "2026-07-05T14:00:00+00:00"),
]


def episode_rows(rows):
    out = []
    for slug, view, total, published in rows:
        fmt = "chapters" if "chapters" in slug else (
            "trial" if "trial" in slug else "battle")
        out.append({
            "video_dir": "videos/" + slug,
            "show": "quill",
            "video_id": "vid-" + slug,
            "title": "Story " + slug + " (Human-Written) | Lost Battles: X",
            "format": fmt,
            "thumbnail_url": "https://rss.thequill.ai/tq/art/x.jpg",
            "published_at": published,
            "duration_seconds": 800,
            "view_count": view,
            "total_view_count": total,
        })
    return out


class Server(socketserver.TCPServer):
    allow_reuse_address = True


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass


def serve():
    httpd = Server((HOST, PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# 1x1 transparent PNG. The fixture's video ids and art paths are invented, so
# i.ytimg.com and rss.thequill.ai would 404 on them and trip the console gate
# with a failure the page did not cause. Stubbed rather than ignored, so the
# gate stays honest about errors that ARE the page's.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c63000100000500010d0a2db40000"
    "000049454e44ae426082")


def install_api(page, rows):
    """Route the episode fetch to a fixture. Glob covers the query string."""
    page.route(
        "**/quill-scheduler.chris-ba5.workers.dev/episodes*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
            body=json.dumps(rows),
        ),
    )
    for pattern in ("**/i.ytimg.com/**", "**/rss.thequill.ai/**"):
        page.route(pattern, lambda route: route.fulfill(
            status=200, content_type="image/png", body=PIXEL))


def check(results, name, ok, detail=""):
    results.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (" - " + detail if detail else ""))
    return ok


def run(shots_dir, live_api):
    results = []
    base = "http://{}:{}/quill/".format(HOST, PORT)

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---------- main pass: real-shaped data ----------
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        install_api(page, episode_rows(FIXTURE))
        page.goto(base, wait_until="networkidle")
        page.wait_for_selector("#episode-list a", timeout=10000)

        print("\nconsolidated number at each count site")
        hero = page.inner_text(".hero-views")
        check(results, "hero shows the total, not the YouTube count",
              "905" in hero.replace(",", "") or "0.9K" in hero, "got: " + repr(hero))

        pop_texts = page.eval_on_selector_all(
            ".popular-views", "els => els.map(e => e.innerText.trim())")
        check(results, "popular cards show K-formatted totals",
              all("K views" in t for t in pop_texts), "got: " + repr(pop_texts))

        row_metas = page.eval_on_selector_all(
            ".row-meta", "els => els.map(e => e.innerText)")
        toller_row = [t for t in row_metas if "2.1K views" in t]
        check(results, "list row shows Toller at 2.1K, not 5",
              len(toller_row) == 1 and " 5 views" not in " ".join(row_metas),
              "rows with 2.1K: {}".format(len(toller_row)))

        print("\nMost Popular ranks on the consolidated number")
        pop_titles = page.eval_on_selector_all(
            ".popular-title", "els => els.map(e => e.innerText)")
        expect = ["toller", "sakurai", "rabe"]
        got = [t.lower() for t in pop_titles]
        check(results, "podium is Toller, Sakurai, Rabe (not Albuera first)",
              len(got) == 3 and all(e in g for e, g in zip(expect, got)),
              "got: " + repr(pop_titles))
        check(results, "Albuera - top by YouTube count - is off the podium",
              not any("albuera" in t for t in got))

        print("\nplatform marks label the number")
        # Derived from the rendered row count, not hardcoded to len(FIXTURE):
        # hero(1) + podium(3) + one per list row. A hardcoded expectation here
        # reads as a page failure the moment the fixture or the real catalog
        # changes size, which is exactly the false alarm this suite exists to
        # avoid raising.
        n_rows = page.eval_on_selector_all("#episode-list > a", "els => els.length")
        expected_groups = 1 + 3 + n_rows
        n_groups = page.eval_on_selector_all(".views-platforms", "els => els.length")
        check(results, "a mark group at every count site",
              n_groups == expected_groups,
              "{} rows -> expected {}, got {}".format(n_rows, expected_groups, n_groups))

        per_group = page.eval_on_selector_all(
            ".views-platforms",
            "els => els.map(e => e.querySelectorAll('svg.platform-icon').length)")
        check(results, "exactly 3 marks in every group",
              per_group == [3] * n_groups, "got: " + repr(set(per_group)))

        # A <use> that fails to resolve still leaves a sized <svg> box, so
        # measuring the box proves nothing (feedback_image_decode_not_bounding_box
        # is the same trap for <img>). Resolve the reference instead.
        resolved = page.evaluate("""() => {
          const uses = [...document.querySelectorAll('svg.platform-icon use')];
          return uses.every(u => {
            const id = (u.getAttribute('href') || '').slice(1);
            const sym = document.getElementById(id);
            return !!sym && sym.tagName.toLowerCase() === 'symbol'
                   && !!sym.querySelector('path');
          });
        }""")
        check(results, "every <use> resolves to a real symbol with a path", resolved)

        painted = page.evaluate("""() => {
          const el = document.querySelector('svg.platform-icon');
          const r = el.getBoundingClientRect();
          return {w: Math.round(r.width), h: Math.round(r.height),
                  fill: getComputedStyle(el).fill,
                  op: getComputedStyle(el).opacity};
        }""")
        check(results, "marks are painted at a legible size",
              8 <= painted["w"] <= 16 and painted["w"] == painted["h"],
              "got: " + repr(painted))

        print("\naccessibility")
        sr = page.eval_on_selector_all(
            ".views-platforms + .sr-only", "els => els.map(e => e.textContent)")
        check(results, "each mark group carries sr-only platform text",
              len(sr) == n_groups
              and all("YouTube, Instagram and TikTok" in t for t in sr),
              "got {} spans for {} groups".format(len(sr), n_groups))
        sr_hidden = page.evaluate("""() => {
          const el = document.querySelector('.sr-only');
          const r = el.getBoundingClientRect();
          return r.width <= 2 && r.height <= 2;
        }""")
        check(results, "sr-only text is visually hidden", sr_hidden)
        check(results, "mark groups are aria-hidden", page.eval_on_selector_all(
            ".views-platforms", "els => els.every(e => e.ariaHidden === 'true')"))

        print("\nlayout")
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        check(results, "no horizontal overflow at 390px", overflow)
        frames = page.eval_on_selector_all(
            ".popular-card .frame",
            "els => els.map(e => Math.round(e.getBoundingClientRect().height))")
        check(results, "Most Popular frames stay level",
              len(set(frames)) == 1, "heights: " + repr(frames))

        shots_dir.mkdir(parents=True, exist_ok=True)
        for label, w, h in [("phone", 390, 844), ("desktop", 1280, 900)]:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(250)
            page.screenshot(path=str(shots_dir / ("quill-views-" + label + ".png")),
                            full_page=True)
        print("\n  screenshots -> {}".format(shots_dir))

        check(results, "no console errors", not errors, repr(errors[:3]))
        ctx.close()

        # ---------- guard: all-null totals still drop Most Popular ----------
        print("\nempty-state guard (all counts null)")
        ctx2 = browser.new_context(viewport={"width": 390, "height": 844})
        page2 = ctx2.new_page()
        null_rows = episode_rows(FIXTURE)
        for r in null_rows:
            r["view_count"] = None
            r["total_view_count"] = None
        install_api(page2, null_rows)
        page2.goto(base, wait_until="networkidle")
        page2.wait_for_selector("#episode-list a", timeout=10000)
        check(results, "Most Popular section is removed, not mislabelled",
              page2.query_selector("#popular-section") is None)
        check(results, "no orphan mark groups without a number",
              page2.eval_on_selector_all(".views-platforms", "els => els.length") == 0)
        ctx2.close()

        # ---------- guard: field absent -> falls back to view_count ----------
        print("\nfallback guard (total_view_count absent from the response)")
        ctx3 = browser.new_context(viewport={"width": 390, "height": 844})
        page3 = ctx3.new_page()
        legacy = episode_rows(FIXTURE)
        for r in legacy:
            del r["total_view_count"]
        install_api(page3, legacy)
        page3.goto(base, wait_until="networkidle")
        page3.wait_for_selector("#episode-list a", timeout=10000)
        metas3 = " ".join(page3.eval_on_selector_all(
            ".row-meta", "els => els.map(e => e.innerText)"))
        check(results, "page degrades to the YouTube count rather than blanking",
              "839 views" in metas3 and "2.1K views" not in metas3)
        check(results, "Most Popular still renders on the fallback",
              page3.query_selector("#popular-section") is not None)
        ctx3.close()

        browser.close()

    if live_api:
        print("\nlive API contract")
        req = urllib.request.Request(API_URL, headers={"User-Agent": "curl/8"})
        rows = json.loads(urllib.request.urlopen(req, timeout=30).read())
        check(results, "every live row carries total_view_count",
              all("total_view_count" in r for r in rows),
              "{} rows".format(len(rows)))
        check(results, "live totals are >= the YouTube counts",
              all((r["total_view_count"] or 0) >= (r["view_count"] or 0) for r in rows))

    failed = [n for n, ok, _ in results if not ok]
    print("\n{}/{} checks passed".format(len(results) - len(failed), len(results)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(ROOT / "scratch" / "quill-views"))
    ap.add_argument("--live-api", action="store_true",
                    help="also assert the real endpoint still returns total_view_count")
    args = ap.parse_args()
    httpd = serve()
    try:
        return run(Path(args.shots), args.live_api)
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
