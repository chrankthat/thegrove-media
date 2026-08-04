#!/usr/bin/env python3
"""Confirm the LIVE site's content-hash meta tag matches the local
build inputs - proof the deploy shipped current content, not just
that the edge returns 200 (feedback_live_hash_verify_via_source_sha_meta.md).
Polls because Cloudflare Pages propagation is not instant."""
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import build_hash          # noqa: E402 - shared digest, single definition

DEFAULT_URL = "https://thegrove.media/"
MAX_ATTEMPTS = 10
DELAY_SECONDS = 20


def live_hash(url):
    req = urllib.request.Request(url, headers={"User-Agent": "thegrove-media-deploy-verify/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
    m = re.search(r'<meta name="x-thegrove-media-source-sha256" content="([a-f0-9]{64})">', body)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()

    expected = build_hash()
    print(f"local build-input sha256: {expected}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        found = live_hash(args.url)
        print(f"attempt {attempt}/{MAX_ATTEMPTS}: live hash = {found}")
        if found == expected:
            print("PASS: live content matches local source")
            sys.exit(0)
        if attempt < MAX_ATTEMPTS:
            time.sleep(DELAY_SECONDS)

    print(f"FAIL: live hash never matched local source after "
          f"{MAX_ATTEMPTS * DELAY_SECONDS}s - deploy did not propagate, or a "
          f"build input changed since the last push+render.")
    sys.exit(1)


if __name__ == "__main__":
    main()
