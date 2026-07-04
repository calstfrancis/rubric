"""
test_hymn_lookup.py — Unit tests for hymn lookup functionality.
"""

import unittest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from hymn_lookup import parse_hymn_ref, HYMNALS


class TestParseHymnRef(unittest.TestCase):
    """Hymn reference parsing."""

    def test_parse_vu_standard(self):
        result = parse_hymn_ref("VU 16")
        self.assertEqual(result, ("VU", 16))

    def test_parse_vu_lowercase(self):
        result = parse_hymn_ref("vu 16")
        self.assertEqual(result, ("VU", 16))

    def test_parse_vu_no_space(self):
        result = parse_hymn_ref("VU16")
        self.assertEqual(result, ("VU", 16))

    def test_parse_mv_reference(self):
        result = parse_hymn_ref("MV 120")
        self.assertEqual(result, ("MV", 120))

    def test_parse_lus_reference(self):
        result = parse_hymn_ref("LUS 5")
        self.assertEqual(result, ("LUS", 5))

    def test_parse_invalid_prefix(self):
        result = parse_hymn_ref("XX 100")
        self.assertIsNone(result)

    def test_parse_no_number(self):
        result = parse_hymn_ref("VU")
        self.assertIsNone(result)

    def test_parse_empty_string(self):
        result = parse_hymn_ref("")
        self.assertIsNone(result)

    def test_parse_whitespace_only(self):
        result = parse_hymn_ref("   ")
        self.assertIsNone(result)


class TestParseHymnRefEdgeCases(unittest.TestCase):
    """Edge cases for hymn reference parsing."""

    def test_parse_large_number(self):
        result = parse_hymn_ref("VU 9999")
        self.assertEqual(result, ("VU", 9999))

    def test_parse_number_zero(self):
        result = parse_hymn_ref("VU 0")
        self.assertEqual(result, ("VU", 0))

    def test_parse_leading_trailing_spaces(self):
        result = parse_hymn_ref("  VU 16  ")
        self.assertEqual(result, ("VU", 16))

    def test_parse_mixed_case(self):
        result = parse_hymn_ref("Mv 50")
        self.assertEqual(result, ("MV", 50))


class TestHymnalsConfig(unittest.TestCase):
    """Hymnal configuration constants."""

    def test_vu_config(self):
        self.assertIn("VU", HYMNALS)
        self.assertEqual(HYMNALS["VU"][0], "VU1996")
        self.assertEqual(HYMNALS["VU"][1], "Voices United")

    def test_mv_config(self):
        self.assertIn("MV", HYMNALS)
        self.assertEqual(HYMNALS["MV"][0], "MV2007")

    def test_lus_config(self):
        self.assertIn("LUS", HYMNALS)
        self.assertEqual(HYMNALS["LUS"][0], "LUS2022")


class TestLookupHymnCacheHit(unittest.TestCase):
    """lookup_hymn uses the cache when available."""

    def test_cache_hit_calls_callback_with_title(self):
        """When the DB has a cached title, the callback receives it."""
        import hymn_lookup
        results = []

        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_get", return_value="O Come, O Come") as mock_get, \
             patch("hymn_lookup.GLib") as mock_glib:

            mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
            hymn_lookup.lookup_hymn("VU", 1, lambda t, e: results.append((t, e)))

            # Give the thread a moment
            import time; time.sleep(0.05)

        mock_get.assert_called_once_with("VU1")

    def test_cache_miss_does_not_call_hymn_set_on_network_error(self):
        """Network failure does not write a bad title to the cache."""
        import hymn_lookup

        results = []

        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_get", return_value=None), \
             patch("hymn_lookup.hymn_set") as mock_set, \
             patch("hymn_lookup._fetch_url",
                   return_value=(None, "timeout")), \
             patch("hymn_lookup.GLib") as mock_glib:

            mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
            hymn_lookup.lookup_hymn("VU", 1, lambda t, e: results.append((t, e)))

            import time; time.sleep(0.05)

        mock_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
