import json
import re
import unittest
from pathlib import Path
from PIL import Image

from scripts.render import build_hash, render_page

ROOT = Path(__file__).resolve().parent.parent.parent
CHANNELS = json.loads((ROOT / "content" / "channels.json").read_text())
ICONS = json.loads((ROOT / "content" / "icons.json").read_text())

EXPECTED = {
    "assets/thegrove-media-badge.png": 320,
    "assets/marks/quill-circle.png": 320,
    "assets/marks/hitl-circle.png": 320,
    "assets/marks/tlf-asis.png": 320,
    "assets/chris-shanku.webp": None,
    "assets/sash-photo.jpg": None,
}


class TestAssets(unittest.TestCase):
    def test_all_referenced_assets_exist(self):
        for rel in EXPECTED:
            self.assertTrue((ROOT / rel).exists(), f"missing {rel}")

    def test_medallion_marks_are_resized_below_max_dimension(self):
        # Rendered at a max of 116 CSS px; 320px raster gives 2x-3x headroom
        # for device pixel ratio without shipping a multi-hundred-KB PNG.
        for rel, max_dim in EXPECTED.items():
            if max_dim is None:
                continue
            with Image.open(ROOT / rel) as img:
                self.assertLessEqual(max(img.size), max_dim, rel)

    def test_image_bytes_are_build_inputs(self):
        # An image-only change MUST move the deploy digest. When it did not,
        # verify_deploy.py printed "PASS: live content matches local source"
        # against the PREVIOUS deploy - a false green that would have shipped a
        # stale mark. Same class the sprint review caught on channels.json.
        before = build_hash()
        target = ROOT / "assets" / "marks" / "hitl-circle.png"
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"\0")
            self.assertNotEqual(
                before, build_hash(),
                "swapping image bytes left the deploy digest unchanged - "
                "verify_deploy.py would false-green against the old deploy",
            )
        finally:
            target.write_bytes(original)
        self.assertEqual(before, build_hash(), "digest not restored")

    def test_every_local_image_url_is_content_hashed(self):
        # /assets/* is `max-age=31536000, immutable` and this Cloudflare token
        # has no purge permission, so an unversioned image URL means a swapped
        # file never reaches a returning visitor or the edge. Proved live
        # 2026-08-05: cf-cache-status HIT, age 32178, on an already-changed file.
        out = render_page(CHANNELS, ICONS)
        local = [
            src for src in re.findall(r'(?:src|href)="([^"]+)"', out)
            if src.startswith("assets/")
        ]
        self.assertTrue(local, "found no local asset URLs - selector is wrong")
        for src in local:
            self.assertRegex(
                src, r"\?v=[0-9a-f]{8}$",
                f"{src} is not content-hashed; an edit to it cannot reach the edge",
            )


if __name__ == "__main__":
    unittest.main()
