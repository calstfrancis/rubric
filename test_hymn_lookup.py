"""
test_hymn_lookup.py — Unit tests for hymn lookup functionality.
"""

import unittest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from hymn_lookup import parse_hymn_ref, HYMNALS, is_in_range, hymn_range


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
    """Hymnal configuration constants.

    HYMNALS maps a book code to its name. It used to map to a
    (hymnary_id, name) pair; the Hymnary identifiers went when the network
    lookup did.
    """

    def test_vu_config(self):
        self.assertIn("VU", HYMNALS)
        self.assertEqual(HYMNALS["VU"], "Voices United")

    def test_mv_config(self):
        self.assertIn("MV", HYMNALS)
        self.assertEqual(HYMNALS["MV"], "More Voices")

    def test_lus_config(self):
        self.assertIn("LUS", HYMNALS)
        self.assertEqual(HYMNALS["LUS"], "Let Us Sing")


class TestRangeChecking(unittest.TestCase):
    """A number outside a hymnal's range can be rejected without a lookup."""

    def test_in_range(self):
        self.assertTrue(is_in_range("VU", 1))
        self.assertTrue(is_in_range("VU", 961))
        self.assertTrue(is_in_range("MV", 217))

    def test_out_of_range(self):
        self.assertFalse(is_in_range("VU", 0))
        self.assertFalse(is_in_range("VU", 962))
        self.assertFalse(is_in_range("MV", 500))

    def test_unknown_book(self):
        self.assertFalse(is_in_range("XYZ", 1))
        self.assertIsNone(hymn_range("XYZ"))


class TestLookupReadsTheDatabase(unittest.TestCase):
    """Lookup is a synchronous local read — no thread, no callback, no network."""

    def test_returns_the_stored_title(self):
        import hymn_lookup
        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_get", return_value="O come, O come, Emmanuel") as mock_get:
            self.assertEqual(hymn_lookup.lookup_hymn("VU", 1),
                             "O come, O come, Emmanuel")
        mock_get.assert_called_once_with("VU1")

    def test_returns_none_when_the_database_lacks_it(self):
        import hymn_lookup
        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_get", return_value=None):
            self.assertIsNone(hymn_lookup.lookup_hymn("VU", 999))

    def test_lowercase_prefix_is_normalised(self):
        import hymn_lookup
        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_get", return_value="x") as mock_get:
            hymn_lookup.lookup_hymn("vu", 1)
        mock_get.assert_called_once_with("VU1")


class TestRememberHymn(unittest.TestCase):
    """Titles the user types in are how the database grows now."""

    def test_stores_a_title(self):
        import hymn_lookup
        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_set") as mock_set:
            self.assertTrue(hymn_lookup.remember_hymn("VU", 1, "  A title  "))
        mock_set.assert_called_once_with("VU1", "A title")

    def test_refuses_a_blank_title(self):
        import hymn_lookup
        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_set") as mock_set:
            self.assertFalse(hymn_lookup.remember_hymn("VU", 1, "   "))
        mock_set.assert_not_called()

    def test_refuses_a_number_outside_the_book(self):
        import hymn_lookup
        with patch.object(hymn_lookup, "_DB_OK", True), \
             patch("hymn_lookup.hymn_set") as mock_set:
            self.assertFalse(hymn_lookup.remember_hymn("VU", 5000, "A title"))
        mock_set.assert_not_called()


class TestNoNetworkCodeRemains(unittest.TestCase):
    """The Hymnary client is gone, not merely unused."""

    def test_module_has_no_fetching_helpers(self):
        import hymn_lookup
        for name in ("_curl_get", "_fetch_url", "_wayback_url",
                     "_extract_hymn_title", "prefetch_hymnal", "PrefetchHandle"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(hymn_lookup, name),
                                 f"hymn_lookup.{name} should have been removed")

    def test_module_imports_nothing_for_networking(self):
        import hymn_lookup
        for name in ("subprocess", "threading", "urllib"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(hymn_lookup, name))


if __name__ == "__main__":
    unittest.main()
