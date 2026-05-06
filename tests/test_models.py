"""
Tests for rubric_package models.
"""

import unittest
import sys
from pathlib import Path
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from rubric_package.models.service import ServiceItem, SectionDivider, entry_from_dict
from rubric_package.models.config import (
    Config,
    SECTIONS,
    DEFAULT_PREAMBLE,
    MAX_UNDO,
    AUTOSAVE_SECS,
    get_palette,
)


class TestServiceItem(unittest.TestCase):
    """ServiceItem data model tests."""

    def test_create_basic(self):
        """Create a basic service item."""
        item = ServiceItem("Opening Hymn", "Gathering")
        self.assertEqual(item.name, "Opening Hymn")
        self.assertEqual(item.section, "Gathering")
        self.assertEqual(item.note, "")
        self.assertEqual(item.leader, "")
        self.assertTrue(item.show_in_bulletin)
        self.assertEqual(item.bulletin_note, "")
        self.assertFalse(item.is_divider)

    def test_create_full(self):
        """Create a service item with all fields."""
        item = ServiceItem(
            name="Sermon",
            section="Word",
            note="Based on John 3:16",
            leader="Rev. Smith",
            show_in_bulletin=False,
            bulletin_note="Message"
        )
        self.assertEqual(item.name, "Sermon")
        self.assertEqual(item.section, "Word")
        self.assertEqual(item.note, "Based on John 3:16")
        self.assertEqual(item.leader, "Rev. Smith")
        self.assertFalse(item.show_in_bulletin)
        self.assertEqual(item.bulletin_note, "Message")

    def test_to_dict(self):
        """Convert to dictionary."""
        item = ServiceItem("Test", "Section", "Note", "Leader")
        d = item.to_dict()
        self.assertEqual(d["type"], "item")
        self.assertEqual(d["name"], "Test")
        self.assertEqual(d["section"], "Section")
        self.assertEqual(d["note"], "Note")
        self.assertEqual(d["leader"], "Leader")
        self.assertTrue(d["show_in_bulletin"])
        self.assertEqual(d["bulletin_note"], "")

    def test_from_dict(self):
        """Create from dictionary."""
        d = {
            "type": "item",
            "name": "Test",
            "section": "Section",
            "note": "Note",
            "leader": "Leader",
            "show_in_bulletin": False,
            "bulletin_note": "Bulletin text"
        }
        item = ServiceItem.from_dict(d)
        self.assertEqual(item.name, "Test")
        self.assertEqual(item.section, "Section")
        self.assertFalse(item.show_in_bulletin)
        self.assertEqual(item.bulletin_note, "Bulletin text")

    def test_from_dict_defaults(self):
        """from_dict uses defaults for missing fields."""
        d = {"type": "item", "name": "Test"}
        item = ServiceItem.from_dict(d)
        self.assertEqual(item.section, "")
        self.assertEqual(item.note, "")
        self.assertEqual(item.leader, "")
        self.assertTrue(item.show_in_bulletin)

    def test_repr(self):
        """String representation."""
        item = ServiceItem("Hymn", "Gathering", leader="Minister")
        r = repr(item)
        self.assertIn("ServiceItem", r)
        self.assertIn("Hymn", r)
        self.assertIn("Minister", r)


class TestSectionDivider(unittest.TestCase):
    """SectionDivider data model tests."""

    def test_create_default(self):
        """Create with default title."""
        div = SectionDivider()
        self.assertEqual(div.title, "New section")
        self.assertTrue(div.is_divider)

    def test_create_custom(self):
        """Create with custom title."""
        div = SectionDivider("Custom Section")
        self.assertEqual(div.title, "Custom Section")

    def test_to_dict(self):
        """Convert to dictionary."""
        div = SectionDivider("My Section")
        d = div.to_dict()
        self.assertEqual(d["type"], "divider")
        self.assertEqual(d["title"], "My Section")

    def test_from_dict(self):
        """Create from dictionary."""
        d = {"type": "divider", "title": "Section Name"}
        div = SectionDivider.from_dict(d)
        self.assertEqual(div.title, "Section Name")

    def test_from_dict_default_title(self):
        """from_dict uses default for missing title."""
        d = {"type": "divider"}
        div = SectionDivider.from_dict(d)
        self.assertEqual(div.title, "Section")

    def test_repr(self):
        """String representation."""
        div = SectionDivider("Test")
        r = repr(div)
        self.assertIn("SectionDivider", r)
        self.assertIn("Test", r)


class TestEntryFromDict(unittest.TestCase):
    """entry_from_dict factory function tests."""

    def test_item_type(self):
        """Parses item type correctly."""
        d = {"type": "item", "name": "Test", "section": "Gathering"}
        result = entry_from_dict(d)
        self.assertIsInstance(result, ServiceItem)
        self.assertEqual(result.name, "Test")

    def test_divider_type(self):
        """Parses divider type correctly."""
        d = {"type": "divider", "title": "New Section"}
        result = entry_from_dict(d)
        self.assertIsInstance(result, SectionDivider)
        self.assertEqual(result.title, "New Section")

    def test_defaults_to_item(self):
        """Defaults to item when type is missing."""
        d = {"name": "Test"}
        result = entry_from_dict(d)
        self.assertIsInstance(result, ServiceItem)


class TestConfig(unittest.TestCase):
    """Config management tests."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a fresh config instance for testing
        self.config = Config.__new__(Config)
        self.config.preamble = DEFAULT_PREAMBLE
        self.config.templates = {}
        self.config.default_template = ""
        self.config.palette = None
        self.config.last_dir = str(Path.home())
        self.config.recent_files = []
        self.config.use_tabs = False
        self.config.last_seen_version = ""
        self.config.bulletin = self.config._default_bulletin()

    def test_default_bulletin_structure(self):
        """Default bulletin has expected structure."""
        bulletin = Config._default_bulletin()
        self.assertIn("church_name", bulletin)
        self.assertIn("staff", bulletin)
        self.assertIn("announcements", bulletin)
        self.assertIsInstance(bulletin["staff"], list)
        self.assertIsInstance(bulletin["announcements"], list)

    def test_add_recent_file(self):
        """Adding recent file updates list."""
        self.config.add_recent("/path/to/file.liturgy")
        self.assertIn("/path/to/file.liturgy", self.config.recent_files)
        self.assertEqual(self.config.recent_files[0], "/path/to/file.liturgy")

    def test_add_recent_moves_existing_to_front(self):
        """Adding existing file moves it to front."""
        self.config.recent_files = ["/file1", "/file2", "/file3"]
        self.config.add_recent("/file2")
        self.assertEqual(self.config.recent_files[0], "/file2")
        self.assertEqual(len(self.config.recent_files), 3)

    def test_add_recent_limits_to_10(self):
        """Recent files list limited to 10 items."""
        for i in range(15):
            self.config.add_recent(f"/file{i}")
        self.assertEqual(len(self.config.recent_files), 10)


class TestSections(unittest.TestCase):
    """SECTIONS constant tests."""

    def test_sections_structure(self):
        """SECTIONS is a list of tuples."""
        self.assertIsInstance(SECTIONS, list)
        self.assertTrue(len(SECTIONS) > 0)
        for section in SECTIONS:
            self.assertIsInstance(section, tuple)
            self.assertEqual(len(section), 2)
            self.assertIsInstance(section[0], str)  # section name
            self.assertIsInstance(section[1], list)  # items list

    def test_standard_sections_present(self):
        """Standard liturgical sections are present."""
        section_names = [s[0] for s in SECTIONS]
        self.assertIn("Gathering", section_names)
        self.assertIn("Word", section_names)
        self.assertIn("Response", section_names)
        self.assertIn("Sending", section_names)


class TestGetPalette(unittest.TestCase):
    """get_palette function tests."""

    def test_returns_default_when_no_palette(self):
        """Returns SECTIONS when config.palette is None."""
        # Use a mock config
        with patch('rubric_package.models.config.config') as mock_config:
            mock_config.palette = None
            result = get_palette()
            self.assertEqual(result, SECTIONS)

    def test_returns_custom_palette(self):
        """Returns custom palette when set."""
        custom = [{"section": "Custom", "items": ["Item1"]}]
        with patch('rubric_package.models.config.config') as mock_config:
            mock_config.palette = custom
            result = get_palette()
            self.assertEqual(result, [("Custom", ["Item1"])])


class TestConstants(unittest.TestCase):
    """Module constants tests."""

    def test_max_undo_positive(self):
        """MAX_UNDO is a positive integer."""
        self.assertIsInstance(MAX_UNDO, int)
        self.assertGreater(MAX_UNDO, 0)

    def test_autosave_seconds_positive(self):
        """AUTOSAVE_SECS is a positive integer."""
        self.assertIsInstance(AUTOSAVE_SECS, int)
        self.assertGreater(AUTOSAVE_SECS, 0)

    def test_default_preamble_contains_latex(self):
        """DEFAULT_PREAMBLE contains LaTeX commands."""
        self.assertIn("\\documentclass", DEFAULT_PREAMBLE)
        self.assertIn("\\usepackage", DEFAULT_PREAMBLE)
        self.assertIn("\\newenvironment{scripture}", DEFAULT_PREAMBLE)


if __name__ == "__main__":
    unittest.main()
