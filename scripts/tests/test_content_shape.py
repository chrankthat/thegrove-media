import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHANNELS = ROOT / "content" / "channels.json"
ICONS = ROOT / "content" / "icons.json"


class TestContentShape(unittest.TestCase):
    def setUp(self):
        self.channels = json.loads(CHANNELS.read_text())
        self.icons = json.loads(ICONS.read_text())

    def test_three_shows_in_locked_order(self):
        names = [s["name"] for s in self.channels["shows"]]
        self.assertEqual(
            names, ["The Quill", "The Little Feather", "Human in the Loop"]
        )

    def test_every_show_has_required_fields(self):
        required = {
            "id", "order", "name", "tagline", "blurb", "extraLine", "role",
            "cohost", "accent", "field", "ink", "display", "body", "mark",
            "watch", "listen", "socials", "cadence", "feeds", "latest",
        }
        for show in self.channels["shows"]:
            missing = required - show.keys()
            self.assertFalse(missing, f"{show['id']} missing {missing}")

    def test_sash_cohost_url_is_buildwithsash(self):
        hitl = next(s for s in self.channels["shows"] if s["id"] == "human-in-the-loop")
        self.assertEqual(hitl["cohost"]["url"], "https://buildwithsash.com")

    def test_every_icon_used_by_a_show_exists_in_icons_json(self):
        used = set()
        for show in self.channels["shows"]:
            for item in show["listen"] + show["socials"]:
                if item.get("icon"):
                    used.add(item["icon"])
        missing = used - self.icons.keys()
        self.assertFalse(missing, f"icons.json missing entries for {missing}")

    def test_cadence_entries_keep_source_and_verified_for_deferred_smoke_predicate(self):
        for show in self.channels["shows"]:
            for entry in show["cadence"]:
                self.assertIn("source", entry)
                self.assertIn("verified", entry)

    def test_no_two_icons_share_a_path(self):
        # Regression: icons.json shipped TuneIn and Amazon Music with identical
        # 113-char paths; the designer's distinct glyphs existed only in the
        # mockup's inline sprite. See fold addendum FOLD-1.
        paths = [e["path"] for e in self.icons.values()]
        self.assertEqual(len(paths), len(set(paths)), "two icons share a path value")

    def test_only_neutral_glyphs_are_flagged_placeholder(self):
        flagged = {k for k, v in self.icons.items() if v.get("placeholder")}
        self.assertEqual(flagged, {"TuneIn", "Amazon Music"})


if __name__ == "__main__":
    unittest.main()
