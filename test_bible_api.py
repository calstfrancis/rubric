"""
tests/test_bible_api.py — Unit tests for Bible reference cleaning.

Note: clean_reference() intentionally converts en/em dashes to ASCII hyphens
because the bible-api.com API requires plain hyphens in range notation.
Tests reflect the actual correct behaviour.

Run with:
    python -m pytest tests/
    python tests/test_bible_api.py
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from bible_api import clean_reference, map_book


class TestCleanReference(unittest.TestCase):
    """Reference string cleaning for the bible-api.com API."""

    def test_removes_optional_brackets(self):
        # [1–9]10–18 → 10-18  (take the part outside the brackets)
        result = clean_reference("[1\u20139]10\u201318")
        self.assertEqual(result, "10-18")

    def test_takes_first_semicolon_segment(self):
        result = clean_reference("Gen 1:1\u20135; Exod 2:1\u20134")
        self.assertEqual(result, "Gen 1:1-5")

    def test_takes_first_comma_segment(self):
        result = clean_reference("Joel 2:1\u20132, 12\u201317")
        self.assertEqual(result, "Joel 2:1-2")

    def test_removes_letter_suffix_lowercase(self):
        result = clean_reference("Ps 23a")
        self.assertNotIn("a", result.split(":")[-1].split(" ")[-1])

    def test_removes_letter_suffix_on_verse(self):
        result = clean_reference("Mark 14:1b")
        self.assertNotIn("b", result.split(":")[-1])

    def test_en_dash_becomes_hyphen(self):
        # En dash (U+2013) → ASCII hyphen
        result = clean_reference("Matt 5:3\u201312")
        self.assertEqual(result, "Matt 5:3-12")

    def test_em_dash_becomes_hyphen(self):
        # Em dash (U+2014) → ASCII hyphen
        result = clean_reference("Matt 5:3\u201412")
        self.assertEqual(result, "Matt 5:3-12")

    def test_non_breaking_space_cleaned(self):
        result = clean_reference("Ps\xa023")
        self.assertNotIn("\xa0", result)

    def test_simple_reference_unchanged(self):
        # A clean reference should pass through (apart from normalisation)
        result = clean_reference("John 3:16")
        self.assertEqual(result, "John 3:16")

    def test_psalm_short(self):
        result = clean_reference("Ps 23")
        self.assertEqual(result, "Ps 23")


class TestMapBook(unittest.TestCase):
    """Book abbreviation expansion for the bible-api.com API."""

    # ── Torah ─────────────────────────────────────────────────────────────────

    def test_genesis(self):
        self.assertEqual(map_book("Gen 1:1"), "Genesis 1:1")

    def test_exodus(self):
        self.assertEqual(map_book("Exod 3:14"), "Exodus 3:14")

    def test_leviticus(self):
        self.assertEqual(map_book("Lev 19:18"), "Leviticus 19:18")

    def test_numbers(self):
        self.assertEqual(map_book("Num 6:24"), "Numbers 6:24")

    def test_deuteronomy(self):
        self.assertEqual(map_book("Deut 6:4"), "Deuteronomy 6:4")

    # ── Historical ────────────────────────────────────────────────────────────

    def test_first_samuel(self):
        self.assertEqual(map_book("1 Sam 3:1"), "1 Samuel 3:1")

    def test_second_kings(self):
        self.assertEqual(map_book("2 Kgs 5:1"), "2 Kings 5:1")

    # ── Psalms ────────────────────────────────────────────────────────────────

    def test_psalm(self):
        self.assertEqual(map_book("Ps 23"), "Psalms 23")

    def test_psalm_with_verses(self):
        self.assertEqual(map_book("Ps 22:1-8"), "Psalms 22:1-8")

    # ── Prophets ──────────────────────────────────────────────────────────────

    def test_isaiah(self):
        self.assertEqual(map_book("Isa 40:1"), "Isaiah 40:1")

    def test_jeremiah(self):
        self.assertEqual(map_book("Jer 31:31"), "Jeremiah 31:31")

    def test_amos(self):
        self.assertEqual(map_book("Amos 8:1"), "Amos 8:1")

    # ── New Testament ─────────────────────────────────────────────────────────

    def test_matthew(self):
        self.assertEqual(map_book("Matt 5:3"), "Matthew 5:3")

    def test_mark(self):
        self.assertEqual(map_book("Mark 1:1"), "Mark 1:1")

    def test_luke(self):
        self.assertEqual(map_book("Luke 4:18"), "Luke 4:18")

    def test_john(self):
        self.assertEqual(map_book("John 3:16"), "John 3:16")

    def test_acts(self):
        self.assertEqual(map_book("Acts 2:1"), "Acts 2:1")

    def test_romans(self):
        self.assertEqual(map_book("Rom 8:1"), "Romans 8:1")

    def test_first_corinthians(self):
        self.assertEqual(map_book("1 Cor 13:1"), "1 Corinthians 13:1")

    def test_revelation(self):
        self.assertEqual(map_book("Rev 3:20"), "Revelation 3:20")

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_unknown_book_passthrough(self):
        # Unknown abbreviation returns unchanged
        result = map_book("Unknown 1:1")
        self.assertEqual(result, "Unknown 1:1")

    def test_already_full_name_passthrough(self):
        # Full book names that don't match an abbreviation pass through
        result = map_book("Genesis 1:1")
        self.assertEqual(result, "Genesis 1:1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
