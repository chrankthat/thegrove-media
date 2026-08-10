import json
import unittest
from pathlib import Path

from scripts.render import render_icon_sprite, render_show

ROOT = Path(__file__).resolve().parent.parent.parent
CHANNELS = json.loads((ROOT / "content" / "channels.json").read_text())
ICONS = json.loads((ROOT / "content" / "icons.json").read_text())

QUILL = next(s for s in CHANNELS["shows"] if s["id"] == "the-quill")
TLF = next(s for s in CHANNELS["shows"] if s["id"] == "the-little-feather")
HITL = next(s for s in CHANNELS["shows"] if s["id"] == "human-in-the-loop")
STUDIO_NAME = CHANNELS["studio"]["name"]


class TestRenderIconSprite(unittest.TestCase):
    def test_sprite_has_a_symbol_per_icon(self):
        sprite = render_icon_sprite(ICONS)
        for label in ICONS:
            self.assertIn(f'id="icon-{label.lower().replace(" ", "-")}"', sprite)


class TestRenderShow(unittest.TestCase):
    def test_section_id_and_field_accent_custom_properties(self):
        out = render_show(QUILL, ICONS, STUDIO_NAME)
        self.assertIn('id="the-quill"', out)
        self.assertIn("--field:#251E19", out)
        self.assertIn("--accent:#C2643A", out)
        self.assertIn("--accent-rgb:194,100,58", out)

    def test_no_cadence_verified_line_rendered(self):
        # Deviation from decision.md D9, ordered by Chris 2026-08-04: the
        # "Verified Aug 4" line must not appear in output, at any breakpoint,
        # even though channels.json still carries the source/verified fields.
        for show in (QUILL, TLF, HITL):
            out = render_show(show, ICONS, STUDIO_NAME)
            self.assertNotIn("Verified", out)
            self.assertNotIn("cadence-verified", out)

    def test_cadence_display_text_still_renders(self):
        out = render_show(QUILL, ICONS, STUDIO_NAME)
        self.assertIn("New stories every Sunday, Tuesday, and Friday.", out)
        self.assertIn("A new My Lost Chapters every month.", out)

    def test_extra_line_renders_only_when_present(self):
        self.assertIn("My Lost Chapters is the exception", render_show(QUILL, ICONS, STUDIO_NAME))
        self.assertNotIn("extra-line", render_show(TLF, ICONS, STUDIO_NAME))

    def test_cohost_renders_only_for_hitl_with_buildwithsash_link(self):
        hitl_out = render_show(HITL, ICONS, STUDIO_NAME)
        self.assertIn("cohost-credit", hitl_out)
        self.assertIn('href="https://buildwithsash.com"', hitl_out)
        self.assertNotIn("linkedin.com/in/shasmo", hitl_out)
        self.assertNotIn("cohost-credit", render_show(QUILL, ICONS, STUDIO_NAME))

    def test_lead_lines_render_only_for_hitl(self):
        hitl_out = render_show(HITL, ICONS, STUDIO_NAME)
        self.assertIn("Two ex-Microsoft builders.", hitl_out)
        self.assertNotIn("lead-lines", render_show(QUILL, ICONS, STUDIO_NAME))

    def test_listen_block_omitted_when_empty(self):
        # None of the three currently has an empty listen[], but the
        # contract (spec S5 field notes) is: omit the whole sidebar-block
        # when listen is empty. Exercise it directly against the function.
        fake_show = dict(QUILL)
        fake_show["listen"] = []
        out = render_show(fake_show, ICONS, STUDIO_NAME)
        self.assertNotIn(">Listen<", out)

    def test_amazon_music_and_tunein_get_generic_icon_labels(self):
        out = render_show(HITL, ICONS, STUDIO_NAME)
        self.assertIn("generic placeholder icon, not an official logo", out)
        self.assertIn("TuneIn (generic icon)", out)
        self.assertIn("Amazon Music (generic icon)", out)

    def test_watch_renders_as_text_links_not_icons(self):
        out = render_show(HITL, ICONS, STUDIO_NAME)
        self.assertIn('<a href="https://www.youtube.com/@humanintheloop.stream"', out)
        self.assertIn("Episode Takeaways", out)

    def test_linkedin_is_not_labelled_a_placeholder(self):
        # LinkedIn carries a provenance `note` but IS an official mark. Keying
        # the placeholder disclosure off `note` mislabelled it. FOLD-1/FOLD-5.
        # No show links LinkedIn as of 2026-08-05, so build one synthetically -
        # the regression is in render_show, not in the data.
        fake_show = dict(HITL)
        fake_show["socials"] = [
            {"label": "LinkedIn", "icon": "LinkedIn", "url": "https://www.linkedin.com/company/example"}
        ]
        out = render_show(fake_show, ICONS, STUDIO_NAME)
        self.assertIn('title="LinkedIn"', out)
        self.assertNotIn("LinkedIn (generic icon)", out)

    def test_every_use_href_resolves_to_a_symbol_in_the_sprite(self):
        sprite = render_icon_sprite(ICONS)
        import re as _re
        for show in (QUILL, TLF, HITL):
            for ref in _re.findall(r'<use href="#(icon-[a-z0-9-]+)">', render_show(show, ICONS, STUDIO_NAME)):
                self.assertIn(f'id="{ref}"', sprite, f"{ref} has no <symbol> in the sprite")

    def test_malformed_color_fails_loud(self):
        bad = dict(QUILL)
        bad["accent"] = '#fff" onload="alert(1)'
        with self.assertRaises(ValueError):
            render_show(bad, ICONS, STUDIO_NAME)

    def test_font_name_with_apostrophe_fails_loud(self):
        # NAME_RE used to allow `'`, but `display`/`body` are interpolated
        # inside a single-quoted CSS custom property
        # (--display:'{name}',serif), so a font literally named O'Sans would
        # close the CSS string early and silently break the rule.
        bad = dict(QUILL)
        bad["display"] = "O'Sans"
        with self.assertRaises(ValueError):
            render_show(bad, ICONS, STUDIO_NAME)

    def test_font_name_with_space_and_hyphen_still_passes(self):
        ok = dict(QUILL)
        ok["display"] = "Some-Font Name"
        out = render_show(ok, ICONS, STUDIO_NAME)
        self.assertIn("--display:'Some-Font Name',serif", out)

    def test_latest_block_omitted_when_empty(self):
        # Same contract as listen: an absent section is honest, a section
        # that says "no episodes" is not (the false-episode-claim fix).
        # None of the three shows in channels.json has `latest` populated
        # today, so this holds for real data too.
        # Uses TLF, not QUILL: the-quill now sets episodeApi (2026-08-10
        # quill-episode-feed-linktree build), so render_show always takes
        # the episodeApi branch for it regardless of `latest`. TLF still
        # has no episodeApi and exercises the honest-when-empty static
        # path this test is named for.
        out = render_show(TLF, ICONS, STUDIO_NAME)
        self.assertNotIn(">Latest Episodes<", out)
        self.assertNotIn("New episodes will appear here", out)
        self.assertNotIn("latest-empty", out)

    def test_latest_block_renders_two_items_escaped(self):
        # Uses TLF, not QUILL, for the same reason as the test above -
        # QUILL now sets episodeApi and would always take that branch,
        # never reaching the static-`latest` path this test exercises.
        fake_show = dict(TLF)
        fake_show["latest"] = ["Episode One <script>", "Episode & Two"]
        out = render_show(fake_show, ICONS, STUDIO_NAME)
        self.assertIn(">Latest Episodes<", out)
        self.assertIn('class="latest-list"', out)
        self.assertIn("Episode One &lt;script&gt;", out)
        self.assertIn("Episode &amp; Two", out)
        self.assertNotIn("<script>", out)

    def test_watch_block_omitted_when_empty(self):
        fake_show = dict(QUILL)
        fake_show["watch"] = []
        out = render_show(fake_show, ICONS, STUDIO_NAME)
        self.assertNotIn(">Watch<", out)

    def test_schedule_block_omitted_when_empty(self):
        fake_show = dict(QUILL)
        fake_show["cadence"] = []
        out = render_show(fake_show, ICONS, STUDIO_NAME)
        self.assertNotIn(">Schedule<", out)


if __name__ == "__main__":
    unittest.main()
