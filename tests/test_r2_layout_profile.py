"""R2: FPT-specific layout and reviewed data require explicit evidence."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reportContent import detect_layout_profile, load_annual_override  # noqa: E402
from util import hash_file  # noqa: E402


class _Page:
    width = 1000
    height = 1000

    def __init__(self, text: str, color: tuple[float, float, float]) -> None:
        self.chars = [{"text": char, "x0": 20 + index * 8,
                       "top": 200, "non_stroking_color": color}
                      for index, char in enumerate(text)]


class R2LayoutProfileTest(unittest.TestCase):
    def test_no_sidebar_is_default_even_when_text_mentions_financials(self) -> None:
        page = _Page("Báo cáo tài chính", (0.0, 0.0, 0.0))
        self.assertEqual(detect_layout_profile(page), ("no_sidebar", None))

    def test_fpt_sidebar_requires_active_blue_label(self) -> None:
        page = _Page("Báo cáo tài chính", (0.02, 0.3, 0.6))
        self.assertEqual(detect_layout_profile(page),
                         ("fpt_sidebar", ("financial", "Báo cáo tài chính")))

    def test_reviewed_override_is_opt_in(self) -> None:
        digest = hash_file(ROOT / "FPT_2024_498332 (1).pdf")
        self.assertIsNone(load_annual_override(None, digest))
        override = load_annual_override(ROOT / "overrides" / "fpt_2024.json", digest)
        self.assertEqual(override["id"], "fpt_2024_reviewed")


if __name__ == "__main__":
    unittest.main()
