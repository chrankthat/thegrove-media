#!/usr/bin/env python3
"""Every external URL in content/channels.json must resolve.

Spec S13: 'the highest-value check in the build' - a dead link on a page posted
in YouTube descriptions is the real failure mode.

Two-stage, because social platforms block non-browser clients: urllib first,
then headless chromium for anything urllib could not settle. A 400 from
facebook.com to a python UA is bot mitigation, not a dead link - verified
2026-08-04, all three Facebook URLs load correctly in a real browser.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNELS = json.loads((ROOT / "content" / "channels.json").read_text())
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Hosts known to reject non-browser clients. Not an exemption - these still get
# checked, just via a real browser instead of urllib.
BROWSER_REQUIRED = ("facebook.com", "instagram.com", "linkedin.com", "tiktok.com")


def collect_urls(channels):
    urls = set()
    studio = channels["studio"]
    urls.add(studio["links"]["personal"])
    urls.add(studio["links"]["company"])
    for link in studio["aboutLinks"]:
        urls.add(link["url"])
    for show in channels["shows"]:
        for item in show["watch"] + show["listen"] + show["socials"]:
            urls.add(item["url"])
        if show.get("cohost"):
            urls.add(show["cohost"]["url"])
        if show["feeds"].get("podcast"):
            urls.add(show["feeds"]["podcast"])
    return sorted(urls)


def is_soft_404(requested, final):
    """A deep link that lands on the site root is a removed resource, not a hit."""
    req_path = urllib.parse.urlparse(requested).path.rstrip("/")
    fin_path = urllib.parse.urlparse(final).path.rstrip("/")
    return bool(req_path) and not fin_path


def check_urllib(url, timeout=20):
    """-> (ok: bool|None, detail). None means 'inconclusive, try a browser'."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if is_soft_404(url, resp.url):
                    return False, f"{resp.status} but redirected to site root: {resp.url}"
                return True, str(resp.status)
        except urllib.error.HTTPError as e:
            if method == "HEAD":
                continue          # many hosts reject HEAD; fall through to GET
            return None, f"HTTP {e.code}"
        except Exception as e:     # noqa: BLE001 - any transport failure is inconclusive
            if method == "HEAD":
                continue
            return None, str(e)
    return None, "no conclusive response"


def check_browser(urls):
    """Load each URL in headless chromium. Returns {url: (ok, detail)}."""
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for url in urls:
            page = browser.new_page()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                title = (page.title() or "").strip()
                status = resp.status if resp else 0
                dead_markers = ("page not found", "content isn't available",
                                "isn't available", "page isn&#x27;t available")
                looks_dead = any(m in title.lower() for m in dead_markers)
                ok = 200 <= status < 400 and title != "" and not looks_dead
                results[url] = (ok, f"browser {status} :: {title[:70]!r}")
            except Exception as e:      # noqa: BLE001
                results[url] = (False, f"browser error :: {e}")
            finally:
                page.close()
        browser.close()
    return results


def main():
    urls = collect_urls(CHANNELS)

    for url in urls:
        scheme = urllib.parse.urlparse(url).scheme
        if scheme != "https":
            print(f"FAIL  non-https scheme {scheme!r}  {url}")
            sys.exit(1)

    deferred, failures = [], []
    for url in urls:
        host = urllib.parse.urlparse(url).netloc
        if any(h in host for h in BROWSER_REQUIRED):
            deferred.append(url)
            continue
        ok, detail = check_urllib(url)
        if ok:
            print(f"PASS  {detail:28} {url}")
        elif ok is False:
            print(f"FAIL  {detail:28} {url}")
            failures.append((url, detail))
        else:
            deferred.append(url)

    if deferred:
        print(f"\n-- {len(deferred)} url(s) inconclusive via urllib, retrying in a browser --")
        for url, (ok, detail) in check_browser(deferred).items():
            print(f"{'PASS' if ok else 'FAIL'}  {detail:60} {url}")
            if not ok:
                failures.append((url, detail))

    print(f"\n{len(urls) - len(failures)}/{len(urls)} links resolved")
    if failures:
        print("FAILURES:")
        for url, detail in failures:
            print(f"  {url} -> {detail}")
        print("\nDo NOT edit a URL in channels.json to make this pass without first "
              "loading it in a browser yourself. This gate has a browser stage "
              "precisely because bot mitigation is not a dead link.")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
