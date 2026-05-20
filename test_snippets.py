"""
test_snippets.py — Unit tests for snippets functionality.
"""

import unittest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from snippets import load_snippets, save_snippets, DEFAULT_SNIPPETS


class TestDefaultSnippets(unittest.TestCase):
    """Default snippet definitions."""

    def test_all_defaults_have_name(self):
        for snippet in DEFAULT_SNIPPETS:
            self.assertIn("name", snippet)
            self.assertIsInstance(snippet["name"], str)
            self.assertTrue(len(snippet["name"]) > 0)

    def test_all_defaults_have_content(self):
        for snippet in DEFAULT_SNIPPETS:
            self.assertIn("content", snippet)
            self.assertIsInstance(snippet["content"], str)

    def test_default_names_unique(self):
        names = [s["name"] for s in DEFAULT_SNIPPETS]
        self.assertEqual(len(names), len(set(names)))

    def test_common_snippets_present(self):
        names = [s["name"] for s in DEFAULT_SNIPPETS]
        self.assertIn("Land acknowledgement (Mi'kmaq)", names)
        self.assertIn("Words of assurance", names)
        self.assertIn("Lord's Prayer (traditional poetic)", names)
        self.assertIn("Benediction", names)


class TestLoadSnippets(unittest.TestCase):
    """load_snippets behaviour with the SQLite backend."""

    def test_seeds_defaults_when_db_empty(self):
        """When the DB has no rows, defaults are seeded and returned."""
        import snippets as snip_mod
        with patch.object(snip_mod, "_DB_OK", True), \
             patch("snippets.snippets_has_data", return_value=False) as mock_has, \
             patch("snippets._db_save") as mock_save, \
             patch("snippets._db_load", return_value=list(DEFAULT_SNIPPETS)) as mock_load:
            result = load_snippets()
            mock_save.assert_called_once()
            mock_load.assert_called_once()
            self.assertEqual(len(result), len(DEFAULT_SNIPPETS))

    def test_returns_stored_snippets_when_db_has_data(self):
        """When the DB already has rows, returns them without re-seeding."""
        stored = [{"name": "Custom", "content": "Custom text"}]
        import snippets as snip_mod
        with patch.object(snip_mod, "_DB_OK", True), \
             patch("snippets.snippets_has_data", return_value=True), \
             patch("snippets._db_save") as mock_save, \
             patch("snippets._db_load", return_value=stored):
            result = load_snippets()
            mock_save.assert_not_called()
            self.assertEqual(result, stored)

    def test_legacy_json_fallback_when_db_unavailable(self):
        """Falls back to JSON file when the DB module is not available."""
        import snippets as snip_mod
        import json
        stored = [{"name": "Legacy", "content": "From JSON"}]
        with patch.object(snip_mod, "_DB_OK", False), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=json.dumps(stored)):
            result = load_snippets()
            self.assertEqual(result[0]["name"], "Legacy")

    def test_legacy_fallback_returns_defaults_when_file_missing(self):
        """Falls back to DEFAULT_SNIPPETS when JSON file is absent and DB unavailable."""
        import snippets as snip_mod
        with patch.object(snip_mod, "_DB_OK", False), \
             patch.object(Path, "exists", return_value=False):
            result = load_snippets()
            self.assertEqual(len(result), len(DEFAULT_SNIPPETS))


class TestSaveSnippets(unittest.TestCase):
    """save_snippets behaviour with the SQLite backend."""

    def test_delegates_to_db_when_available(self):
        """save_snippets calls the db layer when SQLite is available."""
        import snippets as snip_mod
        with patch.object(snip_mod, "_DB_OK", True), \
             patch("snippets._db_save") as mock_save:
            test_snippets = [{"name": "Test", "content": "Content"}]
            save_snippets(test_snippets)
            mock_save.assert_called_once_with(test_snippets)

    def test_legacy_json_fallback_writes_file(self):
        """Falls back to writing JSON when DB is unavailable."""
        import snippets as snip_mod
        import json
        written = []

        def capture(content, **kw):
            written.append(content)

        with patch.object(snip_mod, "_DB_OK", False), \
             patch.object(Path, "mkdir"), \
             patch.object(Path, "write_text", side_effect=capture):
            save_snippets([{"name": "T", "content": "C"}])

        self.assertEqual(len(written), 1)
        parsed = json.loads(written[0])
        self.assertEqual(parsed[0]["name"], "T")


if __name__ == "__main__":
    unittest.main()
