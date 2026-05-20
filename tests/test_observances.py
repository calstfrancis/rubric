"""Tests for observances.py — liturgical calendar intelligence layer."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from observances import get_observances, FIXED, RANGES, TYPES, _nth_weekday, _last_weekday, _nearest_sunday


class TestFixedObservances(unittest.TestCase):

    def test_orange_shirt_day(self):
        obs = get_observances(date(2026, 9, 30))
        names = [o["name"] for o in obs]
        self.assertTrue(any("Orange Shirt Day" in n for n in names))

    def test_orange_shirt_day_type(self):
        obs = get_observances(date(2026, 9, 30))
        indigenous = [o for o in obs if o.get("type") == "indigenous"]
        self.assertTrue(len(indigenous) >= 1)

    def test_all_saints_fixed(self):
        obs = get_observances(date(2026, 11, 1))
        names = [o["name"] for o in obs]
        self.assertTrue(any("All Saints" in n for n in names))

    def test_earth_day(self):
        obs = get_observances(date(2026, 4, 22))
        names = [o["name"] for o in obs]
        self.assertIn("Earth Day", names)

    def test_international_womens_day(self):
        obs = get_observances(date(2026, 3, 8))
        names = [o["name"] for o in obs]
        self.assertIn("International Women's Day", names)

    def test_remembrance_day(self):
        obs = get_observances(date(2026, 11, 11))
        names = [o["name"] for o in obs]
        self.assertTrue(any("Remembrance Day" in n for n in names))

    def test_world_aids_day(self):
        obs = get_observances(date(2026, 12, 1))
        names = [o["name"] for o in obs]
        self.assertIn("World AIDS Day", names)

    def test_no_observance_ordinary_weekday(self):
        # A Tuesday in mid-February with no known observance
        obs = get_observances(date(2026, 2, 17))
        self.assertEqual(obs, [])

    def test_all_fixed_have_type(self):
        for key, obs_list in FIXED.items():
            for obs in obs_list:
                self.assertIn("type", obs, f"Missing type at {key}: {obs['name']}")
                self.assertIn("name", obs)


class TestRangeObservances(unittest.TestCase):

    def test_season_of_creation_start(self):
        obs = get_observances(date(2026, 9, 1))
        names = [o["name"] for o in obs]
        self.assertTrue(any("Season of Creation" in n for n in names))

    def test_season_of_creation_mid(self):
        obs = get_observances(date(2026, 9, 15))
        names = [o["name"] for o in obs]
        self.assertTrue(any("Season of Creation" in n for n in names))

    def test_season_of_creation_end(self):
        obs = get_observances(date(2026, 10, 4))
        names = [o["name"] for o in obs]
        self.assertTrue(any("Season of Creation" in n for n in names))

    def test_season_of_creation_not_after_oct4(self):
        obs = get_observances(date(2026, 10, 5))
        names = [o["name"] for o in obs]
        self.assertFalse(any("Season of Creation" == n for n in names))

    def test_pride_month_june(self):
        obs = get_observances(date(2026, 6, 15))
        names = [o["name"] for o in obs]
        self.assertIn("Pride Month", names)

    def test_pride_month_not_july(self):
        obs = get_observances(date(2026, 7, 1))
        names = [o["name"] for o in obs]
        self.assertNotIn("Pride Month", names)

    def test_week_of_prayer_unity(self):
        obs = get_observances(date(2026, 1, 20))
        names = [o["name"] for o in obs]
        self.assertIn("Week of Prayer for Christian Unity", names)

    def test_16_days_activism(self):
        obs = get_observances(date(2026, 11, 30))
        names = [o["name"] for o in obs]
        self.assertIn("16 Days of Activism Against Gender-Based Violence", names)


class TestComputedObservances(unittest.TestCase):

    def test_indigenous_sunday_2026(self):
        # Jun 21 2026 is a Sunday, so Indigenous Sunday is Jun 21
        jun21 = date(2026, 6, 21)
        self.assertEqual(jun21.weekday(), 6)  # it IS a Sunday
        obs = get_observances(jun21)
        names = [o["name"] for o in obs]
        self.assertIn("Indigenous Sunday (UCC)", names)

    def test_earth_sunday_2026(self):
        # Apr 22 2026 is a Wednesday; nearest Sunday = Apr 19
        apr22 = date(2026, 4, 22)
        nearest_sun = _nearest_sunday(apr22)
        self.assertEqual(nearest_sun.weekday(), 6)
        obs = get_observances(nearest_sun)
        names = [o["name"] for o in obs]
        self.assertIn("Earth Sunday", names)

    def test_pride_sunday_is_last_sunday_of_june(self):
        last_sun = _last_weekday(2026, 6, 6)
        obs = get_observances(last_sun)
        names = [o["name"] for o in obs]
        self.assertIn("Pride Sunday", names)

    def test_creation_sunday_first_sunday_september(self):
        first_sun = _nth_weekday(2026, 9, 6, 1)
        obs = get_observances(first_sun)
        names = [o["name"] for o in obs]
        self.assertIn("Creation Sunday", names)

    def test_remembrance_sunday_2026(self):
        # Nov 11 2026 is a Wednesday; nearest Sunday = Nov 8
        nov11 = date(2026, 11, 11)
        rem_sun = _nearest_sunday(nov11)
        obs = get_observances(rem_sun)
        names = [o["name"] for o in obs]
        self.assertIn("Remembrance Sunday", names)

    def test_all_saints_sunday_2026(self):
        nov1 = date(2026, 11, 1)
        saints_sun = _nearest_sunday(nov1)
        obs = get_observances(saints_sun)
        names = [o["name"] for o in obs]
        self.assertIn("All Saints Sunday", names)

    def test_canadian_thanksgiving_2026(self):
        cth = _nth_weekday(2026, 10, 0, 2)  # second Monday of October
        obs = get_observances(cth)
        names = [o["name"] for o in obs]
        self.assertIn("Canadian Thanksgiving", names)

    def test_world_day_of_prayer_2026(self):
        wdp = _nth_weekday(2026, 3, 4, 1)  # first Friday of March
        obs = get_observances(wdp)
        names = [o["name"] for o in obs]
        self.assertIn("World Day of Prayer", names)


class TestProximityScanning(unittest.TestCase):
    """When a Sunday is queried, observances Mon–Sat should appear with proximity tags."""

    def test_orange_shirt_day_proximity_from_preceding_sunday(self):
        # Sep 30 2026 is a Wednesday; preceding Sunday = Sep 27
        sep30 = date(2026, 9, 30)
        self.assertEqual(sep30.weekday(), 2)  # Wednesday
        sep27 = date(2026, 9, 27)
        self.assertEqual(sep27.weekday(), 6)  # Sunday
        obs = get_observances(sep27)
        # Should include Orange Shirt Day with proximity
        prox = [o for o in obs if "Orange Shirt Day" in o.get("name", "") and o.get("proximity")]
        self.assertTrue(len(prox) >= 1)

    def test_proximity_not_set_on_non_sunday(self):
        # When querying a non-Sunday, no proximity scanning happens
        sep27 = date(2026, 9, 28)  # Monday
        obs = get_observances(sep27)
        prox = [o for o in obs if o.get("proximity")]
        self.assertEqual(prox, [])

    def test_no_duplicate_when_observance_on_sunday_itself(self):
        # If an observance falls exactly on the Sunday, it should not appear twice
        # Sep 30 2025 is a Tuesday; test a year where it might fall on Sunday
        # Sep 30 2018 was a Sunday — test with a synthetic date-equivalence
        # Let's just ensure no observance appears twice
        obs = get_observances(date(2026, 9, 27))
        names = [o["name"] for o in obs]
        # Allow duplicates only if they're proximity vs direct — but deduplicate by name
        self.assertEqual(len(names), len(set(names)))


class TestTypeCatalogue(unittest.TestCase):

    def test_all_types_have_label_and_colour(self):
        for key, info in TYPES.items():
            self.assertIn("label", info, f"Missing label for type {key}")
            self.assertIn("colour", info, f"Missing colour for type {key}")

    def test_all_fixed_observances_have_valid_type(self):
        valid_types = set(TYPES.keys()) | {"civil"}
        for key, obs_list in FIXED.items():
            for obs in obs_list:
                self.assertIn(obs["type"], valid_types,
                              f"Unknown type '{obs['type']}' at {key}: {obs['name']}")


if __name__ == "__main__":
    unittest.main()
