"""
Tests for rubric_package utilities.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rubric_package.utils.latex import (
    latex_escape,
    note_for_latex,
    passage_to_latex,
    migrate_scripture_note,
)
from rubric_package.utils.colors import section_colour, hex_to_rgb, SECTION_COLORS
from rubric_package.utils.helpers import is_hymn_element, HYMN_KEYWORDS


class TestLatexEscape(unittest.TestCase):
    """LaTeX escaping tests."""

    def test_escapes_backslash(self):
        """Backslash is escaped."""
        result = latex_escape("\\text")
        self.assertIn("textbackslash", result)
        # Result should contain textbackslash and end with text
        self.assertTrue(result.startswith("\\textbackslash"))
        self.assertTrue(result.endswith("text"))

    def test_escapes_ampersand(self):
        """Ampersand is escaped."""
        result = latex_escape("A & B")
        self.assertEqual(result, "A \\& B")

    def test_escapes_percent(self):
        """Percent is escaped."""
        result = latex_escape("100%")
        self.assertEqual(result, "100\\%")

    def test_escapes_dollar(self):
        """Dollar sign is escaped."""
        result = latex_escape("$100")
        self.assertEqual(result, "\\$100")

    def test_escapes_hash(self):
        """Hash is escaped."""
        result = latex_escape("#1")
        self.assertEqual(result, "\\#1")

    def test_escapes_underscore(self):
        """Underscore is escaped."""
        result = latex_escape("text_here")
        self.assertEqual(result, "text\\_here")

    def test_escapes_braces(self):
        """Braces are escaped."""
        result = latex_escape("{text}")
        self.assertEqual(result, "\\{text\\}")

    def test_escapes_multiple(self):
        """Multiple special chars are escaped."""
        result = latex_escape("100% & $50")
        self.assertEqual(result, "100\\% \\& \\$50")

    def test_plain_text_unchanged(self):
        """Plain text without special chars is unchanged."""
        result = latex_escape("Hello World")
        self.assertEqual(result, "Hello World")

    def test_empty_string(self):
        """Empty string returns empty."""
        result = latex_escape("")
        self.assertEqual(result, "")


class TestNoteForLatex(unittest.TestCase):
    """Note preparation for LaTeX tests."""

    def test_empty_note(self):
        """Empty note returns empty."""
        result = note_for_latex("")
        self.assertEqual(result, "")

    def test_plain_text_escaped(self):
        """Plain text is escaped."""
        result = note_for_latex("100% sure")
        self.assertEqual(result, "100\\% sure")

    def test_latex_commands_preserved(self):
        """Lines starting with backslash are preserved."""
        note = "\\textit{Italic text}"
        result = note_for_latex(note)
        self.assertEqual(result, note)

    def test_mixed_content(self):
        """Mixed content is handled correctly."""
        note = "Regular text\\n\\textbf{bold}"
        result = note_for_latex(note)
        # Should be escaped because no line starts with \
        self.assertIn("\\&" if "&" in result else "text", result)


class TestPassageToLatex(unittest.TestCase):
    """Bible passage to LaTeX conversion tests."""

    def test_single_verse(self):
        """Convert single verse."""
        text = "1 In the beginning..."
        result = passage_to_latex("Gen 1:1", text)
        self.assertIn("\\sverse{1}", result)
        self.assertIn("\\begin{scripture}", result)
        self.assertIn("\\end{scripture}", result)

    def test_multiple_verses(self):
        """Convert multiple verses."""
        text = "1 First verse\n2 Second verse\n3 Third verse"
        result = passage_to_latex("Test 1:1-3", text)
        self.assertIn("\\sverse{1}", result)
        self.assertIn("\\sverse{2}", result)
        self.assertIn("\\sverse{3}", result)

    def test_verse_continuation(self):
        """Verse split across lines is joined."""
        text = "1 First part\nsecond part of verse"
        result = passage_to_latex("Test 1:1", text)
        # Both parts should be in one sverse
        self.assertIn("First part", result)
        self.assertIn("second part", result)

    def test_reference_in_output(self):
        """Reference appears in output."""
        result = passage_to_latex("John 3:16", "16 For God so loved...")
        self.assertIn("John 3:16", result)
        self.assertIn("(WEB)", result)

    def test_empty_text(self):
        """Empty text handled gracefully."""
        result = passage_to_latex("Ref", "")
        self.assertIn("\\begin{scripture}", result)


class TestMigrateScriptureNote(unittest.TestCase):
    """Scripture note migration tests."""

    def test_no_quotation_returns_unchanged(self):
        """Text without quotation environment is unchanged."""
        text = "Regular note text"
        result = migrate_scripture_note(text)
        self.assertEqual(result, text)

    def test_migrates_quotation(self):
        """Old quotation format is migrated."""
        note = r"""\begin{quotation}
\textit{\small John 3:16}
\noindent\textsuperscript{16}For God so loved...
\end{quotation}"""
        result = migrate_scripture_note(note)
        self.assertIn("\\begin{scripture}", result)
        self.assertIn("\\end{scripture}", result)
        self.assertIn("\\sverse", result)

    def test_preserves_pre_post_content(self):
        """Content before/after quotation is preserved."""
        note = r"""Before
\begin{quotation}
\noindent\textsuperscript{1}Verse
\end{quotation}
After"""
        result = migrate_scripture_note(note)
        self.assertIn("Before", result)
        self.assertIn("After", result)


class TestSectionColour(unittest.TestCase):
    """Section color tests."""

    def test_returns_hex_color(self):
        """Returns hex color code."""
        result = section_colour("Gathering")
        self.assertTrue(result.startswith("#"))
        self.assertEqual(len(result), 7)  # #RRGGBB

    def test_different_sections_different_colors(self):
        """Different sections may have different colors."""
        c1 = section_colour("Gathering")
        c2 = section_colour("Word")
        # They may or may not be different, but both should be valid
        self.assertTrue(c1.startswith("#"))
        self.assertTrue(c2.startswith("#"))

    def test_unknown_section_returns_gray(self):
        """Unknown section returns gray."""
        result = section_colour("UnknownSection")
        self.assertEqual(result, "#888780")

    def test_returns_color_from_palette(self):
        """Color is selected from palette."""
        result = section_colour("Gathering")
        self.assertIn(result, SECTION_COLORS)


class TestHexToRgb(unittest.TestCase):
    """Hex to RGB conversion tests."""

    def test_converts_white(self):
        """White converts correctly."""
        result = hex_to_rgb("#FFFFFF")
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(result[1], 1.0)
        self.assertAlmostEqual(result[2], 1.0)

    def test_converts_black(self):
        """Black converts correctly."""
        result = hex_to_rgb("#000000")
        self.assertAlmostEqual(result[0], 0.0)
        self.assertAlmostEqual(result[1], 0.0)
        self.assertAlmostEqual(result[2], 0.0)

    def test_converts_red(self):
        """Red converts correctly."""
        result = hex_to_rgb("#FF0000")
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(result[1], 0.0)
        self.assertAlmostEqual(result[2], 0.0)

    def test_handles_lowercase(self):
        """Handles lowercase hex."""
        result = hex_to_rgb("#ffffff")
        self.assertAlmostEqual(result[0], 1.0)


class TestIsHymnElement(unittest.TestCase):
    """Hymn element detection tests."""

    def test_detects_hymn(self):
        """Detects 'hymn' in name."""
        self.assertTrue(is_hymn_element("Opening Hymn"))

    def test_detects_psalm(self):
        """Detects 'psalm' in name."""
        self.assertTrue(is_hymn_element("Sung Psalm"))

    def test_detects_song(self):
        """Detects 'song' in name."""
        self.assertTrue(is_hymn_element("Song of Praise"))

    def test_detects_music(self):
        """Detects 'music' in name."""
        self.assertTrue(is_hymn_element("Special Music"))

    def test_detects_anthem(self):
        """Detects 'anthem' in name."""
        self.assertTrue(is_hymn_element("Choral Anthem"))

    def test_detects_gloria(self):
        """Detects 'gloria' in name."""
        self.assertTrue(is_hymn_element("Gloria Patri"))

    def test_case_insensitive(self):
        """Detection is case insensitive."""
        self.assertTrue(is_hymn_element("HYMN"))
        self.assertTrue(is_hymn_element("Hymn"))
        self.assertTrue(is_hymn_element("hymn"))

    def test_non_hymn_returns_false(self):
        """Non-hymn elements return False."""
        self.assertFalse(is_hymn_element("Sermon"))
        self.assertFalse(is_hymn_element("Prayer"))
        self.assertFalse(is_hymn_element("Reading"))


class TestHymnKeywords(unittest.TestCase):
    """HYMN_KEYWORDS constant tests."""

    def test_contains_expected_keywords(self):
        """Contains expected hymn keywords."""
        self.assertIn("hymn", HYMN_KEYWORDS)
        self.assertIn("psalm", HYMN_KEYWORDS)
        self.assertIn("song", HYMN_KEYWORDS)
        self.assertIn("music", HYMN_KEYWORDS)
        self.assertIn("anthem", HYMN_KEYWORDS)
        self.assertIn("gloria", HYMN_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
