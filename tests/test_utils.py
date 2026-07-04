"""
Tests for rubric_package utilities.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rubric_package.utils.typst import (
    typst_escape,
    note_for_typst,
    passage_to_typst,
    strip_typst_for_html,
    strip_typst_plain,
    notes_preview,
)
from rubric_package.utils.colors import section_colour, hex_to_rgb, SECTION_COLORS
from rubric_package.utils.helpers import is_hymn_element, HYMN_KEYWORDS
from rubric_package.utils.rich_typst import process_inline, TAG_BOLD, TAG_ITALIC


class TestTypstEscape(unittest.TestCase):
    """Typst escaping tests."""

    def test_escapes_hash(self):
        """Hash is escaped."""
        result = typst_escape("#1")
        self.assertEqual(result, "\\#1")

    def test_escapes_asterisk(self):
        """Asterisk is escaped."""
        result = typst_escape("*bold*")
        self.assertEqual(result, "\\*bold\\*")

    def test_escapes_underscore(self):
        """Underscore is escaped."""
        result = typst_escape("text_here")
        self.assertEqual(result, "text\\_here")

    def test_escapes_at(self):
        """At-sign is escaped."""
        result = typst_escape("@label")
        self.assertEqual(result, "\\@label")

    def test_escapes_dollar(self):
        """Dollar sign is escaped."""
        result = typst_escape("$100")
        self.assertEqual(result, "\\$100")

    def test_escapes_angle_brackets(self):
        """Angle brackets are escaped."""
        result = typst_escape("<tag>")
        self.assertEqual(result, "\\<tag\\>")

    def test_escapes_multiple(self):
        """Multiple special chars are all escaped."""
        result = typst_escape("#1 *bold* _em_")
        self.assertEqual(result, "\\#1 \\*bold\\* \\_em\\_")

    def test_plain_text_unchanged(self):
        """Plain text without special chars is unchanged."""
        result = typst_escape("Hello World")
        self.assertEqual(result, "Hello World")

    def test_empty_string(self):
        """Empty string returns empty."""
        result = typst_escape("")
        self.assertEqual(result, "")


class TestNoteForTypst(unittest.TestCase):
    """Note preparation for Typst tests."""

    def test_empty_note(self):
        """Empty note returns empty."""
        result = note_for_typst("")
        self.assertEqual(result, "")

    def test_plain_text_escaped(self):
        """Plain text with special chars is escaped."""
        result = note_for_typst("Pray for #1")
        self.assertEqual(result, "Pray for \\#1")

    def test_typst_commands_preserved(self):
        """Notes with Typst function calls are passed through as-is."""
        note = "#scripture[\n  #sverse(1)[In the beginning...]\n]"
        result = note_for_typst(note)
        self.assertEqual(result, note)

    def test_typst_passthrough_on_hash_at_line_start(self):
        """A line starting with #letter triggers passthrough."""
        note = "Some text\n#ldr[Leader: Say this]"
        result = note_for_typst(note)
        self.assertEqual(result, note)

    def test_plain_multiline_escaped(self):
        """Plain multiline text without # at line start is escaped."""
        note = "Line one\nLine two"
        result = note_for_typst(note)
        self.assertEqual(result, note)  # no special chars to escape


class TestPassageToTypst(unittest.TestCase):
    """Bible passage to Typst conversion tests."""

    def test_single_verse(self):
        """Convert single verse produces sverse and scripture blocks."""
        text = "1 In the beginning..."
        result = passage_to_typst("Gen 1:1", text)
        self.assertIn("#sverse(1)", result)
        self.assertIn("#scripture[", result)
        self.assertIn("In the beginning", result)

    def test_multiple_verses(self):
        """Multiple verses each get their own sverse."""
        text = "1 First verse\n2 Second verse\n3 Third verse"
        result = passage_to_typst("Test 1:1-3", text)
        self.assertIn("#sverse(1)", result)
        self.assertIn("#sverse(2)", result)
        self.assertIn("#sverse(3)", result)

    def test_verse_continuation_joined(self):
        """Continuation lines are joined into the same sverse."""
        text = "1 First part\nsecond part of verse"
        result = passage_to_typst("Test 1:1", text)
        self.assertIn("First part", result)
        self.assertIn("second part", result)
        self.assertEqual(result.count("#sverse"), 1)

    def test_reference_in_output(self):
        """Reference and translation label appear in the header line."""
        result = passage_to_typst("John 3:16", "16 For God so loved...", "web")
        self.assertIn("John 3:16", result)
        self.assertIn("(WEB)", result)

    def test_translation_label_uppercase(self):
        """Translation key is uppercased in the label."""
        result = passage_to_typst("Ps 23:1", "1 The Lord is my shepherd", "esv")
        self.assertIn("(ESV)", result)

    def test_empty_text(self):
        """Empty verse text produces a scripture block with no sverse lines."""
        result = passage_to_typst("Ref", "")
        self.assertIn("#scripture[", result)
        self.assertNotIn("#sverse", result)

    def test_special_chars_in_reference_escaped(self):
        """Special Typst chars in the reference are escaped."""
        result = passage_to_typst("Ps 23:1 #special", "1 Text")
        self.assertIn("\\#special", result)


class TestStripTypstForHtml(unittest.TestCase):
    """strip_typst_for_html tests."""

    def test_scripture_content_preserved(self):
        """Verse text content is preserved when stripping scripture markup."""
        text = "#scripture[\n  #sverse(1)[In the beginning]\n]"
        result = strip_typst_for_html(text)
        self.assertIn("In the beginning", result)

    def test_scripture_nested_brackets_multi_verse(self):
        """All sverse content preserved when scripture has multiple nested brackets."""
        text = "#scripture[\n  #sverse(1)[First verse]\n  #sverse(2)[Second verse]\n]"
        result = strip_typst_for_html(text)
        self.assertIn("First verse", result)
        self.assertIn("Second verse", result)

    def test_leader_note_with_strong_stripped(self):
        """#leader-note containing #strong[...] is fully stripped."""
        text = "#leader-note[say *this* and #strong[that]]"
        result = strip_typst_for_html(text)
        self.assertNotIn("this", result)
        self.assertNotIn("that", result)

    def test_bold_markup(self):
        """*bold* becomes <strong>."""
        result = strip_typst_for_html("*hello*")
        self.assertIn("<strong>hello</strong>", result)

    def test_italic_markup(self):
        """_italic_ becomes <em>."""
        result = strip_typst_for_html("_hello_")
        self.assertIn("<em>hello</em>", result)

    def test_leader_note_stripped(self):
        """#leader-note[...] is removed entirely."""
        result = strip_typst_for_html("#leader-note[For the minister only]")
        self.assertNotIn("For the minister only", result)
        self.assertNotIn("#leader-note", result)

    def test_plain_text_unchanged(self):
        """Plain text passes through."""
        result = strip_typst_for_html("Hello World")
        self.assertEqual(result, "Hello World")


class TestStripTypstPlain(unittest.TestCase):
    """strip_typst_plain tests."""

    def test_scripture_to_plain(self):
        """#scripture block becomes plain numbered verse text."""
        text = "#scripture[\n  #sverse(1)[In the beginning]\n]"
        result = strip_typst_plain(text)
        self.assertIn("In the beginning", result)

    def test_leader_note_stripped(self):
        """#leader-note[...] is removed entirely."""
        result = strip_typst_plain("#leader-note[Private note]")
        self.assertNotIn("Private note", result)

    def test_bold_markup_stripped(self):
        """*bold* is stripped to plain text."""
        result = strip_typst_plain("*hello*")
        self.assertIn("hello", result)
        self.assertNotIn("*", result)

    def test_italic_markup_stripped(self):
        """_italic_ is stripped to plain text."""
        result = strip_typst_plain("_hello_")
        self.assertIn("hello", result)
        self.assertNotIn("_", result)


class TestNotesPreview(unittest.TestCase):
    """notes_preview tests."""

    def test_short_text_unchanged(self):
        self.assertEqual(notes_preview("Short note."), "Short note.")

    def test_empty_text_returns_empty(self):
        self.assertEqual(notes_preview(""), "")

    def test_collapses_whitespace(self):
        self.assertEqual(notes_preview("line one\n\n   line two"), "line one line two")

    def test_truncates_on_word_boundary_with_ellipsis(self):
        text = "word " * 60  # far longer than the default 200-char limit
        result = notes_preview(text)
        self.assertTrue(result.endswith("…"))
        self.assertNotIn(" …", result[-3:])  # no dangling space before the ellipsis
        # Every remaining "word" before the ellipsis should be a whole word, not chopped
        self.assertTrue(result[:-1].split()[-1] == "word")

    def test_respects_custom_limit(self):
        result = notes_preview("one two three four five", limit=10)
        self.assertTrue(len(result) <= 11)  # 10 + ellipsis
        self.assertTrue(result.endswith("…"))

    def test_strips_typst_markup(self):
        result = notes_preview("*bold* and _italic_ text")
        self.assertNotIn("*", result)
        self.assertNotIn("_", result)


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
        self.assertTrue(is_hymn_element("Opening Hymn"))

    def test_detects_psalm(self):
        self.assertTrue(is_hymn_element("Sung Psalm"))

    def test_detects_song(self):
        self.assertTrue(is_hymn_element("Song of Praise"))

    def test_detects_music(self):
        self.assertTrue(is_hymn_element("Special Music"))

    def test_detects_anthem(self):
        self.assertTrue(is_hymn_element("Choral Anthem"))

    def test_detects_gloria(self):
        self.assertTrue(is_hymn_element("Gloria Patri"))

    def test_case_insensitive(self):
        self.assertTrue(is_hymn_element("HYMN"))
        self.assertTrue(is_hymn_element("Hymn"))
        self.assertTrue(is_hymn_element("hymn"))

    def test_non_hymn_returns_false(self):
        self.assertFalse(is_hymn_element("Sermon"))
        self.assertFalse(is_hymn_element("Prayer"))
        self.assertFalse(is_hymn_element("Reading"))


class TestHymnKeywords(unittest.TestCase):
    """HYMN_KEYWORDS constant tests."""

    def test_contains_expected_keywords(self):
        self.assertIn("hymn", HYMN_KEYWORDS)
        self.assertIn("psalm", HYMN_KEYWORDS)
        self.assertIn("song", HYMN_KEYWORDS)
        self.assertIn("music", HYMN_KEYWORDS)
        self.assertIn("anthem", HYMN_KEYWORDS)
        self.assertIn("gloria", HYMN_KEYWORDS)


class TestProcessInline(unittest.TestCase):
    """process_inline pure-Python unit tests."""

    def test_plain_text_no_tags(self):
        result = process_inline("Hello world")
        self.assertEqual(result, [("Hello world", frozenset())])

    def test_bold(self):
        result = process_inline("*bold*")
        self.assertEqual(result, [("bold", frozenset({TAG_BOLD}))])

    def test_italic(self):
        result = process_inline("_italic_")
        self.assertEqual(result, [("italic", frozenset({TAG_ITALIC}))])

    def test_mixed(self):
        result = process_inline("say *bold* and _italic_")
        texts = [frag for frag, _ in result]
        self.assertIn("bold", texts)
        self.assertIn("italic", texts)
        bold_tags = [tags for frag, tags in result if frag == "bold"][0]
        italic_tags = [tags for frag, tags in result if frag == "italic"][0]
        self.assertIn(TAG_BOLD, bold_tags)
        self.assertIn(TAG_ITALIC, italic_tags)

    def test_strong_fn_normalised_to_bold(self):
        result = process_inline("#strong[word]")
        self.assertEqual(result, [("word", frozenset({TAG_BOLD}))])

    def test_emph_fn_normalised_to_italic(self):
        result = process_inline("#emph[word]")
        self.assertEqual(result, [("word", frozenset({TAG_ITALIC}))])

    def test_empty(self):
        result = process_inline("")
        self.assertEqual(result, [])

    def test_surrounding_text_preserved(self):
        result = process_inline("before *bold* after")
        all_text = "".join(frag for frag, _ in result)
        self.assertEqual(all_text, "before bold after")
        bold_frags = [f for f, t in result if TAG_BOLD in t]
        self.assertEqual(bold_frags, ["bold"])


if __name__ == "__main__":
    unittest.main()
