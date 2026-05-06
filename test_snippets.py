"""
tests/test_snippets.py — Unit tests for snippets functionality.

Run with:
    python -m pytest tests/
    python tests/test_snippets.py
"""

import unittest
from pathlib import Path
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from snippets import (
    load_snippets,
    save_snippets,
    DEFAULT_SNIPPETS,
    SNIPPETS_PATH,
)


class TestLoadSnippets(unittest.TestCase):
    """Loading snippets from disk."""

    def test_load_returns_defaults_when_file_missing(self):
        """When snippets file doesn't exist, return defaults."""
        with patch.object(Path, 'exists', return_value=False):
            result = load_snippets()
            self.assertEqual(len(result), len(DEFAULT_SNIPPETS))
            self.assertEqual(result[0]["name"], DEFAULT_SNIPPETS[0]["name"])

    def test_load_parses_existing_file(self):
        """Load and parse existing snippets file."""
        custom_snippets = [
            {"name": "Custom", "content": "Test content"}
        ]
        mock_content = json.dumps(custom_snippets)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value=mock_content):
                result = load_snippets()
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["name"], "Custom")
                self.assertEqual(result[0]["content"], "Test content")

    def test_load_returns_defaults_on_invalid_json(self):
        """On invalid JSON, return default snippets."""
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value="invalid json"):
                result = load_snippets()
                self.assertEqual(len(result), len(DEFAULT_SNIPPETS))

    def test_load_returns_defaults_on_empty_file(self):
        """On empty file, return default snippets."""
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value=""):
                result = load_snippets()
                self.assertEqual(len(result), len(DEFAULT_SNIPPETS))

    def test_load_returns_copy_of_defaults(self):
        """Loading returns a copy, not the original DEFAULT_SNIPPETS list."""
        with patch.object(Path, 'exists', return_value=False):
            result = load_snippets()
            # Result should be a different list object
            self.assertIsNot(result, DEFAULT_SNIPPETS)


class TestSaveSnippets(unittest.TestCase):
    """Saving snippets to disk."""

    def test_save_creates_directory(self):
        """Saving creates parent directory."""
        mock_mkdir = MagicMock()
        mock_write = MagicMock()

        with patch.object(Path, 'mkdir', mock_mkdir):
            with patch.object(Path, 'write_text', mock_write):
                test_snippets = [{"name": "Test", "content": "Content"}]
                save_snippets(test_snippets)
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_save_writes_json(self):
        """Saving writes valid JSON."""
        written_content = []

        def capture_write(content, **kwargs):
            written_content.append(content)

        with patch.object(Path, 'mkdir'):
            with patch.object(Path, 'write_text', side_effect=capture_write):
                test_snippets = [{"name": "Test", "content": "Content"}]
                save_snippets(test_snippets)

                self.assertEqual(len(written_content), 1)
                # Verify it's valid JSON
                parsed = json.loads(written_content[0])
                self.assertEqual(parsed[0]["name"], "Test")

    def test_save_preserves_unicode(self):
        """Saving preserves Unicode characters."""
        written_content = []

        def capture_write(content, **kwargs):
            written_content.append(content)
            # Check encoding parameter
            self.assertEqual(kwargs.get('encoding'), 'utf-8')

        with patch.object(Path, 'mkdir'):
            with patch.object(Path, 'write_text', side_effect=capture_write):
                test_snippets = [{"name": "Unicode", "content": "café 🎵"}]
                save_snippets(test_snippets)


class TestDefaultSnippets(unittest.TestCase):
    """Default snippet definitions."""

    def test_all_defaults_have_name(self):
        """All default snippets have a name field."""
        for snippet in DEFAULT_SNIPPETS:
            self.assertIn("name", snippet)
            self.assertIsInstance(snippet["name"], str)
            self.assertTrue(len(snippet["name"]) > 0)

    def test_all_defaults_have_content(self):
        """All default snippets have a content field."""
        for snippet in DEFAULT_SNIPPETS:
            self.assertIn("content", snippet)
            self.assertIsInstance(snippet["content"], str)

    def test_default_names_unique(self):
        """Default snippet names are unique."""
        names = [s["name"] for s in DEFAULT_SNIPPETS]
        self.assertEqual(len(names), len(set(names)))

    def test_common_snippets_present(self):
        """Common liturgical snippets are included."""
        names = [s["name"] for s in DEFAULT_SNIPPETS]
        self.assertIn("Land acknowledgement (Mi'kmaq)", names)
        self.assertIn("Words of assurance", names)
        self.assertIn("Lord's Prayer (traditional poetic)", names)
        self.assertIn("Benediction", names)


if __name__ == "__main__":
    unittest.main()
