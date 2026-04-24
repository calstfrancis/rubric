"""
tests/test_rcl_data.py — Unit tests for RCL date calculations.

Run with:
    python -m pytest tests/
    python tests/test_rcl_data.py
"""

import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from rcl_data import (
    easter,
    advent_sunday,
    lectionary_year,
    get_liturgical_info,
    _proper_for_date,
)


class TestEaster(unittest.TestCase):
    """Easter date calculation (Anonymous Gregorian algorithm)."""

    def test_easter_2024(self):
        self.assertEqual(easter(2024), date(2024, 3, 31))

    def test_easter_2025(self):
        self.assertEqual(easter(2025), date(2025, 4, 20))

    def test_easter_2026(self):
        self.assertEqual(easter(2026), date(2026, 4, 5))

    def test_easter_2027(self):
        self.assertEqual(easter(2027), date(2027, 3, 28))

    def test_easter_2028(self):
        self.assertEqual(easter(2028), date(2028, 4, 16))


class TestAdventSunday(unittest.TestCase):
    """Advent Sunday (4th Sunday before Christmas)."""

    def test_advent_2024(self):
        self.assertEqual(advent_sunday(2024), date(2024, 12, 1))

    def test_advent_2025(self):
        self.assertEqual(advent_sunday(2025), date(2025, 11, 30))

    def test_advent_2026(self):
        self.assertEqual(advent_sunday(2026), date(2026, 11, 29))

    def test_advent_is_sunday(self):
        for year in range(2020, 2030):
            d = advent_sunday(year)
            self.assertEqual(d.weekday(), 6, f"Advent {year} is not a Sunday: {d}")


class TestLectionaryYear(unittest.TestCase):
    """Lectionary year (A/B/C) — transitions on Advent Sunday, not Jan 1."""

    def test_year_b_advent_2023(self):
        # Advent 2023 (Dec 3) starts Year B
        self.assertEqual(lectionary_year(date(2023, 12, 3)), "B")

    def test_year_b_christmas_2023(self):
        # Christmas 2023 still Year B (after Advent started)
        self.assertEqual(lectionary_year(date(2023, 12, 25)), "B")

    def test_year_c_advent_2024(self):
        # Advent 2024 (Dec 1) starts Year C
        self.assertEqual(lectionary_year(date(2024, 12, 1)), "C")

    def test_year_b_mid_2024(self):
        # Between Advent 2023 and Advent 2024 = Year B
        self.assertEqual(lectionary_year(date(2024, 6, 1)), "B")

    def test_year_c_mid_2025(self):
        self.assertEqual(lectionary_year(date(2025, 6, 1)), "C")

    def test_year_a_mid_2026(self):
        self.assertEqual(lectionary_year(date(2026, 6, 1)), "A")

    def test_three_year_cycle(self):
        # A → B → C → A
        years = [lectionary_year(date(2020 + i, 6, 1)) for i in range(6)]
        # Should cycle through A, B, C
        self.assertEqual(len(set(years)), 3)


class TestProperForDate(unittest.TestCase):
    """Proper number assignment during Ordinary Time."""

    def test_proper_4_june_1(self):
        self.assertEqual(_proper_for_date(date(2024, 6, 1)), 4)

    def test_proper_4_may_28(self):
        self.assertEqual(_proper_for_date(date(2024, 5, 28)), 4)

    def test_proper_29_nov_23(self):
        self.assertEqual(_proper_for_date(date(2024, 11, 23)), 29)

    def test_proper_29_nov_19(self):
        self.assertEqual(_proper_for_date(date(2024, 11, 19)), 29)

    def test_proper_in_range(self):
        # All Propers should be between 4 and 29
        for d in [date(2024, 6, 1), date(2024, 7, 1), date(2024, 9, 1), date(2024, 11, 1)]:
            p = _proper_for_date(d)
            self.assertGreaterEqual(p, 4)
            self.assertLessEqual(p, 29)


class TestGetLiturgicalInfo(unittest.TestCase):
    """Full liturgical info dict for specific dates."""

    # ── Lent ──────────────────────────────────────────────────────────────────

    def test_ash_wednesday_2024_season(self):
        info = get_liturgical_info(date(2024, 2, 14))
        self.assertEqual(info["season"], "Lent")

    def test_ash_wednesday_2024_week(self):
        info = get_liturgical_info(date(2024, 2, 14))
        self.assertEqual(info["week"], "Ash Wednesday")

    def test_lent_has_readings(self):
        info = get_liturgical_info(date(2024, 3, 10))  # Lent 4
        self.assertTrue(info["found"])
        self.assertNotEqual(info["gospel"], "—")

    # ── Holy Week ─────────────────────────────────────────────────────────────

    def test_palm_sunday_2024_season(self):
        info = get_liturgical_info(date(2024, 3, 24))
        self.assertEqual(info["season"], "Palm Sunday")

    def test_good_friday_2024(self):
        info = get_liturgical_info(date(2024, 3, 29))
        self.assertTrue(info["found"])
        self.assertEqual(info["season"], "Good Friday")

    # ── Easter ────────────────────────────────────────────────────────────────

    def test_easter_sunday_2024_season(self):
        info = get_liturgical_info(date(2024, 3, 31))
        self.assertEqual(info["season"], "Easter")

    def test_easter_sunday_2024_week(self):
        info = get_liturgical_info(date(2024, 3, 31))
        self.assertIn("Easter Sunday", info["week"])

    def test_easter_has_readings(self):
        info = get_liturgical_info(date(2024, 3, 31))
        self.assertTrue(info["found"])
        self.assertNotEqual(info["gospel"], "—")

    # ── Advent ────────────────────────────────────────────────────────────────

    def test_advent_1_2024_season(self):
        info = get_liturgical_info(date(2024, 12, 1))
        self.assertEqual(info["season"], "Advent")

    def test_advent_has_readings(self):
        info = get_liturgical_info(date(2024, 12, 1))
        self.assertTrue(info["found"])
        self.assertNotEqual(info["gospel"], "—")

    # ── Christmas ─────────────────────────────────────────────────────────────

    def test_christmas_2024(self):
        info = get_liturgical_info(date(2024, 12, 25))
        self.assertEqual(info["season"], "Christmas")
        self.assertTrue(info["found"])

    # ── Ordinary Time ─────────────────────────────────────────────────────────

    def test_ordinary_time_season(self):
        info = get_liturgical_info(date(2024, 7, 14))
        self.assertEqual(info["season"], "Ordinary")

    def test_ordinary_time_has_proper(self):
        info = get_liturgical_info(date(2024, 7, 14))
        self.assertIn("Proper", info["week"])

    def test_ordinary_time_has_readings(self):
        info = get_liturgical_info(date(2024, 7, 14))
        self.assertTrue(info["found"])

    # ── Colour ────────────────────────────────────────────────────────────────

    def test_advent_colour_purple(self):
        info = get_liturgical_info(date(2024, 12, 1))
        # Purple/violet for Advent
        self.assertIn(info["colour"].lower(), ["purple", "violet"])

    def test_easter_colour_white(self):
        info = get_liturgical_info(date(2024, 3, 31))
        # rcl_data returns "white / gold" for Easter
        self.assertIn("white", info["colour"].lower())

    def test_ordinary_colour_green(self):
        info = get_liturgical_info(date(2024, 7, 14))
        self.assertEqual(info["colour"].lower(), "green")

    def test_lent_colour_purple(self):
        info = get_liturgical_info(date(2024, 3, 10))
        self.assertIn(info["colour"].lower(), ["purple", "violet"])

    # ── Lectionary year in info dict ──────────────────────────────────────────

    def test_year_in_info(self):
        info = get_liturgical_info(date(2024, 7, 14))
        self.assertIn(info["year"], ["A", "B", "C"])

    def test_year_b_easter_2024(self):
        info = get_liturgical_info(date(2024, 3, 31))
        self.assertEqual(info["year"], "B")


if __name__ == "__main__":
    unittest.main(verbosity=2)
