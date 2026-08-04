import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent

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


if __name__ == "__main__":
    unittest.main()
