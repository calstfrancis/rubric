"""Tests for the element content model (rubric_package/models/content.py).

Content used to be a Typst string edited through a rich-text costume. The
translation was lossy in one direction — anything the parser didn't recognise
was shown to the user verbatim — so services filled up with `#linebreak()`
nobody typed. Content is now a list of blocks and Typst is an output format.

What these tests protect:

* Nothing that isn't text can reach the editor. The block model has no field
  for markup, so this is mostly about the *migration* path from old files.
* Migration loses no words.
* text -> Typst -> text is stable, so opening and saving a service repeatedly
  can't drift (blank lines multiplying around leader blocks was a real bug).
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rubric_package.models.content import (
    blocks_to_html,
    blocks_to_plain,
    blocks_to_typst,
    concat,
    is_empty,
    make_block,
    make_run,
    normalise,
    plain_to_blocks,
    typst_to_blocks,
)


class TestNormalise(unittest.TestCase):
    """Files are user-editable JSON, so loading must never raise."""

    def test_non_list_becomes_empty(self):
        self.assertEqual(normalise("not a list"), [])
        self.assertEqual(normalise(None), [])

    def test_unknown_block_type_degrades_to_paragraph(self):
        self.assertEqual(normalise([{"type": "marquee", "runs": []}]),
                         [{"type": "p", "runs": []}])

    def test_junk_runs_are_dropped(self):
        blocks = normalise([{"type": "p", "runs": ["bare string", {"text": 7}, {"text": "ok"}]}])
        self.assertEqual(blocks, [{"type": "p", "runs": [{"text": "ok"}]}])

    def test_is_empty_ignores_whitespace(self):
        self.assertTrue(is_empty([make_block("p", [make_run("   ")])]))
        self.assertFalse(is_empty([make_block("p", [make_run("x")])]))


class TestPlainText(unittest.TestCase):

    def test_each_line_becomes_a_paragraph(self):
        self.assertEqual(plain_to_blocks("a\nb"),
                         [{"type": "p", "runs": [{"text": "a"}]},
                          {"type": "p", "runs": [{"text": "b"}]}])

    def test_plain_round_trip(self):
        self.assertEqual(blocks_to_plain(plain_to_blocks("one\ntwo\n\nthree")),
                         "one\ntwo\n\nthree")

    def test_leader_blocks_can_be_excluded(self):
        blocks = [make_block("p", [make_run("said")]),
                  make_block("leader", [make_run("whispered")])]
        self.assertEqual(blocks_to_plain(blocks, include_leader=False), "said")

    def test_concat_separates_with_a_blank_line(self):
        self.assertEqual(blocks_to_plain(concat(plain_to_blocks("a"), plain_to_blocks("b"))),
                         "a\n\nb")


class TestTypstOutput(unittest.TestCase):

    def test_headings_and_lists(self):
        blocks = [make_block("h1", [make_run("Title")]),
                  make_block("h2", [make_run("Sub")]),
                  make_block("bullet", [make_run("item")]),
                  make_block("ordered", [make_run("first")])]
        self.assertEqual(blocks_to_typst(blocks), "= Title\n== Sub\n- item\n+ first")

    def test_inline_emphasis(self):
        blocks = [make_block("p", [make_run("Leader:", bold=True), make_run(" go", italic=True)])]
        self.assertEqual(blocks_to_typst(blocks), "*Leader:* _go_ \\")

    def test_emphasis_padding_moves_outside_the_markers(self):
        """Typst won't emphasise a span that opens or closes on whitespace."""
        out = blocks_to_typst([make_block("p", [make_run("  spaced  ", bold=True)])])
        self.assertTrue(out.startswith("  *spaced*  "))

    def test_whitespace_only_run_is_not_emphasised(self):
        out = blocks_to_typst([make_block("p", [make_run("   ", bold=True)])])
        self.assertNotIn("*", out)

    def test_leader_blocks_wrap_together(self):
        blocks = [make_block("leader", [make_run("one")]),
                  make_block("leader", [make_run("two")]),
                  make_block("p", [make_run("spoken")])]
        self.assertEqual(blocks_to_typst(blocks),
                         "#leader-note[one \\\ntwo]\nspoken \\")

    def test_typst_syntax_typed_by_the_user_is_escaped(self):
        """A user typing #linebreak() means those characters, not a call."""
        out = blocks_to_typst([make_block("p", [make_run("#linebreak()")])])
        self.assertTrue(out.startswith("\\#linebreak()"))


class TestHtmlOutput(unittest.TestCase):

    def test_lists_are_grouped(self):
        blocks = [make_block("bullet", [make_run("a")]), make_block("bullet", [make_run("b")])]
        self.assertEqual(blocks_to_html(blocks), "<ul>\n<li>a</li>\n<li>b</li>\n</ul>")

    def test_leader_omitted_from_the_bulletin_by_default(self):
        blocks = [make_block("leader", [make_run("private")]),
                  make_block("p", [make_run("public")])]
        self.assertNotIn("private", blocks_to_html(blocks))
        self.assertIn("private", blocks_to_html(blocks, include_leader=True))

    def test_html_is_escaped(self):
        self.assertIn("&lt;b&gt;", blocks_to_html([make_block("p", [make_run("<b>")])]))


class TestMigrationFromTypst(unittest.TestCase):
    """Reading services written before the block model."""

    def test_headings_lists_and_emphasis(self):
        blocks = typst_to_blocks("= Title\n- item\n*bold* rest")
        self.assertEqual([b["type"] for b in blocks], ["h1", "bullet", "p"])
        self.assertTrue(blocks[2]["runs"][0]["bold"])

    def test_leader_note_becomes_leader_blocks(self):
        blocks = typst_to_blocks("spoken\n#leader-note[quiet]\nmore")
        self.assertEqual([b["type"] for b in blocks], ["p", "leader", "p"])

    def test_linebreak_call_becomes_a_real_break(self):
        blocks = typst_to_blocks("alpha#linebreak()beta")
        self.assertEqual(blocks_to_plain(blocks), "alpha\nbeta")

    def test_layout_calls_never_appear_as_text(self):
        text = blocks_to_plain(typst_to_blocks("a#h(1em)b\n#colbreak()\nc"))
        for call in ("#h(", "#colbreak", "#linebreak", "#v("):
            self.assertNotIn(call, text)

    def test_unknown_call_survives_as_literal_text(self):
        """Migration never silently deletes wording it doesn't understand."""
        self.assertIn("#lorem(100)", blocks_to_plain(typst_to_blocks("#lorem(100)")))


class TestRoundTripStability(unittest.TestCase):
    """Open, save, open again must not drift.

    Blank lines used to multiply around leader blocks on every cycle, because
    the newline separating a `#leader-note[...]` from its neighbours was read
    back as an empty paragraph.
    """

    CASES = [
        "spoken\n#leader-note[quiet]\nmore",
        "#leader-note[Preamble]\nFriends, \\\nand all",
        "#leader-note[one]\n#leader-note[two]\ntext",
        "= Head\n\n- a\n- b\n\n*bold*",
        "#lorem(100)",
        "",
    ]

    def test_blocks_are_fixed_under_repeated_round_trips(self):
        for src in self.CASES:
            with self.subTest(src=src):
                first = typst_to_blocks(src)
                second = typst_to_blocks(blocks_to_typst(first))
                third = typst_to_blocks(blocks_to_typst(second))
                self.assertEqual(first, second)
                self.assertEqual(second, third)

    def test_empty_blocks_lose_their_kind(self):
        """A blank line is a blank line, whatever it was typed inside.

        A GtkTextBuffer cannot hold a tag over a zero-length range, so an empty
        styled block comes back from the editor as a plain one. Normalising in
        the model keeps the two in agreement — otherwise merely selecting an
        element registered as an edit.
        """
        self.assertEqual(normalise([{"type": "leader", "runs": []}]),
                         [{"type": "p", "runs": []}])
        self.assertEqual(normalise([{"type": "h1", "runs": [{"text": "  "}]}])[0]["type"], "p")

    def test_no_blank_line_growth_around_leader_blocks(self):
        blocks = typst_to_blocks("#leader-note[Preamble]\nFriends,")
        for _ in range(5):
            blocks = typst_to_blocks(blocks_to_typst(blocks))
        self.assertEqual(len(blocks), 2)


try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    from rubric_package.utils.rich_typst import blocks_to_buffer, buffer_to_blocks
    _GTK_OK = True
except Exception:
    _GTK_OK = False


@unittest.skipUnless(_GTK_OK, "GTK4 typelibs not available")
class TestEditorBufferRoundTrip(unittest.TestCase):
    """Blocks -> GtkTextBuffer -> blocks, the editor's own conversion.

    This had no test, and a dead-code sweep removed the two lookup tables it
    depends on: the regex matched from one `def` to the next and the module
    constants happened to sit between them. Every call raised NameError, the
    element editor rendered nothing, and nothing in the suite noticed.
    """

    CASES = {
        "heading": [make_block("h1", [make_run("Head")])],
        "bold and plain runs": [make_block("p", [make_run("Leader:", bold=True),
                                                 make_run(" go")])],
        "italic": [make_block("p", [make_run("quietly", italic=True)])],
        "leader note": [make_block("leader", [make_run("stand")])],
        "bullets": [make_block("bullet", [make_run("one")]),
                    make_block("bullet", [make_run("two")])],
        "ordered": [make_block("ordered", [make_run("first")])],
        "blank line between": [make_block("p", [make_run("a")]),
                               make_block("p", []),
                               make_block("p", [make_run("b")])],
        "every block type": [make_block(t, [make_run(t)]) for t in
                             ("p", "h1", "h2", "h3", "bullet", "ordered", "leader")],
    }

    def test_round_trip_is_exact(self):
        for name, blocks in self.CASES.items():
            with self.subTest(case=name):
                buf = Gtk.TextBuffer()
                blocks_to_buffer(blocks, buf)
                self.assertEqual(buffer_to_blocks(buf), blocks)

    def test_bullet_marker_is_display_only(self):
        """The bullet glyph is shown but is not part of the text."""
        buf = Gtk.TextBuffer()
        blocks_to_buffer([make_block("bullet", [make_run("one")])], buf)
        shown = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        self.assertTrue(shown.startswith("\u2022 "))
        self.assertEqual(buffer_to_blocks(buf)[0]["runs"], [{"text": "one"}])


if __name__ == "__main__":
    unittest.main()
