import copy
import json
import re
import unittest
from pathlib import Path

from scripts.render import render_page

ROOT = Path(__file__).resolve().parent.parent.parent
CHANNELS_PATH = ROOT / "content" / "channels.json"
ICONS_PATH = ROOT / "content" / "icons.json"
CHANNELS = json.loads(CHANNELS_PATH.read_text())
ICONS = json.loads(ICONS_PATH.read_text())


class TestRenderPage(unittest.TestCase):
    def setUp(self):
        self.out = render_page(CHANNELS, ICONS)

    def test_no_script_tags_while_latest_episodes_is_disabled(self):
        # Chris switched Latest Episodes off on 2026-08-11 pending a redesign,
        # so channels.json ships latestEpisodesEnabled: false and the page is
        # back to zero application JS. Pinned because a disabled section that
        # still ships its widget script is the failure mode this flag exists to
        # avoid - a fetch and a parse for markup that is not on the page.
        scripts = re.findall(r"<script[^>]*>", self.out)
        self.assertEqual(scripts, [], f"expected zero <script> tags, found {scripts}")
        self.assertNotIn("Latest Episodes", self.out)
        self.assertNotIn("latest-list", self.out)
        self.assertNotIn("cdn.tailwindcss.com", self.out)

    def test_enabling_latest_episodes_restores_exactly_one_hashed_script(self):
        # The widget invariant, kept under test while the section is off so the
        # eventual redesign starts from a green baseline rather than rediscovering
        # it: exactly one script tag, same-origin, content-hashed like every other
        # /assets/* reference, deferred, nothing third-party or CDN-hosted.
        channels = copy.deepcopy(CHANNELS)
        channels["latestEpisodesEnabled"] = True
        out = render_page(channels, ICONS)

        scripts = re.findall(r"<script[^>]*>", out)
        self.assertEqual(len(scripts), 1, f"expected exactly one <script> tag, found {scripts}")
        tag = scripts[0]
        self.assertRegex(
            tag, r'src="assets/latest-episodes\.js\?v=[0-9a-f]{8}"',
            f"widget script is not same-origin and content-hashed: {tag}",
        )
        self.assertIn("defer", tag)
        self.assertNotIn("http://", tag)
        self.assertNotIn("https://", tag)
        self.assertIn("Latest Episodes", out)
        self.assertIn('<ul class="latest-list" data-episode-api', out)

    def test_shows_appear_in_locked_order(self):
        quill_pos = self.out.index('id="the-quill"')
        tlf_pos = self.out.index('id="the-little-feather"')
        hitl_pos = self.out.index('id="human-in-the-loop"')
        self.assertLess(quill_pos, tlf_pos)
        self.assertLess(tlf_pos, hitl_pos)

    def test_studio_tagline_and_about_present(self):
        self.assertIn("The best stories are never about the big thing", self.out)
        # esc(..., quote=True) turns the apostrophe into &#x27; - assert the
        # escaped form, which is what correct output actually contains.
        self.assertIn("I&#x27;m Chris Shanku.", self.out)
        self.assertIn('href="https://shanku.net"', self.out)
        self.assertIn('href="https://thegrove.llc"', self.out)

    def test_content_hash_meta_changes_when_a_build_input_changes(self):
        # A real regression test, not a tautology: the old version compared
        # build_hash() against the value render_page already generated using
        # build_hash(), so it could never fail. This perturbs a real build
        # input (css/site.css) on disk, confirms the meta hash tracks it,
        # then restores the file and confirms the hash reverts too.
        # try/finally guarantees a failure here cannot leave a dirty file.
        from scripts.render import build_hash, render_page

        css_path = ROOT / "css" / "site.css"
        original_css = css_path.read_text()
        original_hash = build_hash()
        try:
            css_path.write_text(original_css + "\n/* test perturbation */\n")
            perturbed_hash = build_hash()
            self.assertNotEqual(original_hash, perturbed_hash)

            perturbed_page = render_page(CHANNELS, ICONS)
            self.assertIn(
                f'<meta name="x-thegrove-media-source-sha256" content="{perturbed_hash}">',
                perturbed_page,
            )
        finally:
            css_path.write_text(original_css)

        self.assertEqual(build_hash(), original_hash)

    def test_generated_marker_and_canonical_present(self):
        self.assertIn("GENERATED FILE - DO NOT EDIT DIRECTLY", self.out)
        self.assertIn('<link rel="canonical" href="https://thegrove.media/">', self.out)

    def test_committed_index_html_is_not_stale(self):
        # Catches both hand-edits of index.html and a forgotten render.py run.
        index = ROOT / "index.html"
        if not index.exists():
            self.skipTest("index.html not generated yet (first run of this test file)")
        self.assertEqual(
            index.read_text(), self.out,
            "index.html on disk differs from render_page() output - "
            "run `python3 scripts/render.py` and commit the result",
        )

    def test_css_files_linked_not_tailwind_cdn(self):
        self.assertIn('href="css/tokens.css?v=', self.out)
        self.assertIn('href="css/site.css?v=', self.out)
        self.assertNotIn("cdn.tailwindcss.com", self.out)

    def test_css_hrefs_are_content_hashed(self):
        # _headers caches /css/* for 24h and this Cloudflare token has no
        # purge permission - the version query string is what makes a CSS
        # edit actually reach the edge. Confirm both hrefs carry an 8-hex-char
        # ?v= value, not just the literal prefix.
        import re
        for stylesheet in ("css/tokens.css", "css/site.css"):
            match = re.search(
                rf'href="{re.escape(stylesheet)}\?v=([0-9a-f]{{8}})"', self.out
            )
            self.assertIsNotNone(
                match, f"expected a hashed ?v= query string on {stylesheet}"
            )

    def test_no_cadence_verified_anywhere_in_full_page(self):
        self.assertNotIn("Verified Aug", self.out)

    def test_about_has_mobile_eyebrow(self):
        self.assertIn('class="about-eyebrow"', self.out)


if __name__ == "__main__":
    unittest.main()
