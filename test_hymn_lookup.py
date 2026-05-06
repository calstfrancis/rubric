"""
tests/test_hymn_lookup.py — Unit tests for hymn lookup functionality.

Run with:
    python -m pytest tests/
    python tests/test_hymn_lookup.py
"""

import unittest
from pathlib import Path
import sys
import json
from unittest.mock import patch, MagicMock
import io

sys.path.insert(0, str(Path(__file__).parent))

from hymn_lookup import (
    parse_hymn_ref,
    HYMNALS,
    _load_cache,
    _save_cache,
    CACHE_PATH,
)


class TestParseHymnRef(unittest.TestCase):
    """Hymn reference parsing."""

    def test_parse_vu_standard(self):
        """Parse standard Voices United reference."""
        result = parse_hymn_ref("VU 16")
        self.assertEqual(result, ("VU", 16))

    def test_parse_vu_lowercase(self):
        """Parse lowercase reference."""
        result = parse_hymn_ref("vu 16")
        self.assertEqual(result, ("VU", 16))

    def test_parse_vu_no_space(self):
        """Parse reference without space."""
        result = parse_hymn_ref("VU16")
        self.assertEqual(result, ("VU", 16))

    def test_parse_mv_reference(self):
        """Parse More Voices reference."""
        result = parse_hymn_ref("MV 120")
        self.assertEqual(result, ("MV", 120))

    def test_parse_lus_reference(self):
        """Parse Let Us Sing reference."""
        result = parse_hymn_ref("LUS 5")
        self.assertEqual(result, ("LUS", 5))

    def test_parse_invalid_prefix(self):
        """Invalid hymnbook prefix returns None."""
        result = parse_hymn_ref("XX 100")
        self.assertIsNone(result)

    def test_parse_no_number(self):
        """Reference without number returns None."""
        result = parse_hymn_ref("VU")
        self.assertIsNone(result)

    def test_parse_empty_string(self):
        """Empty string returns None."""
        result = parse_hymn_ref("")
        self.assertIsNone(result)

    def test_parse_whitespace_only(self):
        """Whitespace-only string returns None."""
        result = parse_hymn_ref("   ")
        self.assertIsNone(result)


class TestHymnalsConfig(unittest.TestCase):
    """Hymnal configuration."""

    def test_vu_config(self):
        """Voices United has correct config."""
        self.assertIn("VU", HYMNALS)
        self.assertEqual(HYMNALS["VU"][0], "VU1996")
        self.assertEqual(HYMNALS["VU"][1], "Voices United")

    def test_mv_config(self):
        """More Voices has correct config."""
        self.assertIn("MV", HYMNALS)
        self.assertEqual(HYMNALS["MV"][0], "MV2007")

    def test_lus_config(self):
        """Let Us Sing has correct config."""
        self.assertIn("LUS", HYMNALS)
        self.assertEqual(HYMNALS["LUS"][0], "LUS2022")


class TestCache(unittest.TestCase):
    """Cache operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.original_cache = None
        # Don't touch real cache file

    def test_load_cache_nonexistent(self):
        """Loading non-existent cache returns empty dict."""
        with patch.object(Path, 'exists', return_value=False):
            result = _load_cache()
            self.assertEqual(result, {})

    def test_load_cache_valid(self):
        """Loading valid cache returns parsed data."""
        test_data = {"VU:1": "Test Hymn"}
        mock_content = json.dumps(test_data)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value=mock_content):
                result = _load_cache()
                self.assertEqual(result, test_data)

    def test_load_cache_invalid_json(self):
        """Loading invalid JSON returns empty dict."""
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value="invalid json"):
                result = _load_cache()
                self.assertEqual(result, {})

    def test_save_cache_creates_directory(self):
        """Saving cache creates parent directory."""
        mock_mkdir = MagicMock()
        mock_write = MagicMock()

        with patch.object(Path, 'mkdir', mock_mkdir):
            with patch.object(Path, 'write_text', mock_write):
                test_cache = {}
                _save_cache(test_cache, "VU:1", "Test Hymn")
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestParseHymnRefEdgeCases(unittest.TestCase):
    """Edge cases for hymn reference parsing."""

    def test_parse_large_number(self):
        """Parse hymn with large number."""
        result = parse_hymn_ref("VU 9999")
        self.assertEqual(result, ("VU", 9999))

    def test_parse_number_zero(self):
        """Parse hymn number zero."""
        result = parse_hymn_ref("VU 0")
        self.assertEqual(result, ("VU", 0))

    def test_parse_leading_trailing_spaces(self):
        """Parse with leading/trailing whitespace."""
        result = parse_hymn_ref("  VU 16  ")
        self.assertEqual(result, ("VU", 16))

    def test_parse_mixed_case(self):
        """Parse mixed case reference."""
        result = parse_hymn_ref("Mv 50")
        self.assertEqual(result, ("MV", 50))


if __name__ == "__main__":
    unittest.main()
