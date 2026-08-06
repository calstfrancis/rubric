"""Regression tests for what the bulletin actually prints.

Every test here would have failed at fa11e5f ("drop Typst as the editing
model"), the commit that switched the bulletin renderers from ``content_typst``
to ``content_plain``. That one substitution silently removed four guarantees at
once — leader notes stopped being excluded, formatting was flattened, Typst
markup stopped being escaped, and HTML stopped being escaped — because none of
them had a test. The manuscript renderers were not touched by that commit and
stayed correct, so several tests below assert the two agree.

The leader-note case is the one to keep: those are private notes for whoever is
presiding, and the failure mode is printing them for the congregation.
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from rubric_package.models.config import config
from rubric_package.models.service import ServiceItem
from rubric_package.models.content import (
    make_block, make_run, blocks_to_typst, blocks_to_plain, blocks_to_html,
    plain_to_blocks, typst_to_blocks,
)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw
    Adw.init()
    from rubric_package.exporters.bulletin_exporter import BulletinExporter
    _GTK_OK = True
except Exception as e:  # pragma: no cover - environment without GTK
    _GTK_OK = False
    _SKIP_REASON = f"GTK/libadwaita unavailable: {e}"
else:
    _SKIP_REASON = ""


_patchers = []


def setUpModule():
    # config.save() writes to the user's real ~/.config/rubric/config.json.
    p = patch.object(config, "save", lambda *a, **k: None)
    p.start()
    _patchers.append(p)


def tearDownModule():
    for p in _patchers:
        p.stop()
    _patchers.clear()


def _item_with_leader_note():
    """An element mixing spoken text with a private instruction."""
    si = ServiceItem("Prayers of the People", "Response")
    si.content = [
        make_block("p", [make_run("Let us pray for the world.")]),
        make_block("leader", [make_run("PRIVATE: pause, nod to the organist")]),
        make_block("p", [make_run("Hear our prayer.")]),
    ]
    return si


class TestLeaderNotesStayOutOfTheBulletin(unittest.TestCase):
    """The one invariant worth protecting above all the others here."""

    def test_bulletin_typst_excludes_leader_notes(self):
        si = _item_with_leader_note()
        self.assertNotIn("PRIVATE", si.content_typst_bulletin)
        self.assertIn("Let us pray for the world.", si.content_typst_bulletin)

    def test_bulletin_plain_excludes_leader_notes(self):
        si = _item_with_leader_note()
        self.assertNotIn("PRIVATE", si.content_plain_bulletin)

    def test_manuscript_typst_still_includes_them(self):
        """The leader's own copy is the one place they belong."""
        si = _item_with_leader_note()
        self.assertIn("PRIVATE", si.content_typst)
        self.assertIn("#leader-note[", si.content_typst)

    def test_bulletin_html_excludes_leader_notes(self):
        si = _item_with_leader_note()
        self.assertNotIn("PRIVATE", blocks_to_html(si.content))
        self.assertIn("PRIVATE", blocks_to_html(si.content, include_leader=True))

    def test_element_holding_only_a_leader_note_reads_as_empty(self):
        """So the bulletin prints a heading with no orphaned body under it."""
        si = ServiceItem("Silence", "Word")
        si.content = [make_block("leader", [make_run("wait ten seconds")])]
        self.assertEqual(si.content_plain_bulletin.strip(), "")
        self.assertEqual(si.content_typst_bulletin.strip(), "")


class TestBulletinKeepsFormatting(unittest.TestCase):
    """Bold, italic, headings and lists survive into the bulletin.

    They were flattened to a single run of plain text, while the manuscript kept
    them — so the same element printed differently in the two documents.
    """

    def _formatted(self):
        si = ServiceItem("Call to Worship", "Gathering")
        si.content = [
            make_block("p", [make_run("Leader:", bold=True), make_run(" Come.")]),
            make_block("p", [make_run("All: And also with you.", italic=True)]),
            make_block("h2", [make_run("A Heading")]),
            make_block("bullet", [make_run("A bullet")]),
        ]
        return si

    def test_bulletin_typst_keeps_emphasis_headings_and_lists(self):
        out = self._formatted().content_typst_bulletin
        self.assertIn("*Leader:*", out)
        self.assertIn("_All: And also with you._", out)
        self.assertIn("== A Heading", out)
        self.assertIn("- A bullet", out)

    def test_bulletin_html_keeps_emphasis_headings_and_lists(self):
        out = blocks_to_html(self._formatted().content)
        self.assertIn("<strong>", out)
        self.assertIn("<em>", out)
        self.assertIn("<h2>", out)
        self.assertIn("<li>", out)

    def test_bulletin_and_manuscript_agree_when_there_is_no_leader_note(self):
        """With nothing private to strip, the two renderings are identical."""
        si = self._formatted()
        self.assertEqual(si.content_typst_bulletin, si.content_typst)


class TestTypstEscapingInContent(unittest.TestCase):
    """Characters Typst reads as markup must survive as the user typed them."""

    def _typst_for(self, text):
        return blocks_to_typst(plain_to_blocks(text))

    def test_email_address_is_escaped(self):
        """Unescaped, Typst reads @hopeunited as a reference to a missing label."""
        self.assertIn(r"office\@hopeunited.ca", self._typst_for("office@hopeunited.ca"))

    def test_asterisks_do_not_become_bold(self):
        self.assertIn(r"\*Please stand\*", self._typst_for("*Please stand*"))

    def test_underscores_do_not_become_italic(self):
        self.assertIn(r"\_quiet\_", self._typst_for("_quiet_"))

    def test_angle_brackets_are_escaped(self):
        self.assertIn(r"\<John 3:16\>", self._typst_for("<John 3:16>"))

    def test_tilde_and_backtick_are_escaped(self):
        self.assertIn(r"\~", self._typst_for("Silence ~ then"))
        self.assertIn(r"\`code\`", self._typst_for("`code`"))

    def test_hash_and_dollar_are_still_escaped(self):
        self.assertIn(r"\#linebreak()", self._typst_for("#linebreak()"))
        self.assertIn(r"\$20", self._typst_for("$20"))

    def test_emphasis_from_run_styling_is_not_escaped(self):
        """Styling is carried by the run, so its markers are real markup."""
        out = blocks_to_typst([make_block("p", [make_run("shout", bold=True)])])
        self.assertIn("*shout*", out)
        self.assertNotIn(r"\*", out)

    def test_literal_markers_survive_a_full_round_trip(self):
        """Escaping must not accumulate backslashes on load/save cycles."""
        for text in ["*not bold*", "office@church.ca", "a ~ b", "<tag>", "`tick`"]:
            with self.subTest(text=text):
                blocks = plain_to_blocks(text)
                once = typst_to_blocks(blocks_to_typst(blocks))
                twice = typst_to_blocks(blocks_to_typst(once))
                self.assertEqual(blocks, once)
                self.assertEqual(once, twice)
                self.assertEqual(blocks_to_plain(once), text)


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestRenderedBulletinDocument(unittest.TestCase):
    """The assembled documents, not just the content helpers."""

    def _exporter(self, item):
        main = MagicMock()
        main.service_entries = [item]
        main.service_title_entry.get_text.return_value = "Test Service"
        main.selected_date = None
        # No hand-written bulletin override — these tests are about what Rubric
        # generates from the service order.
        main.service_bulletin_text = ""
        main._load_typst_preamble.return_value = ""
        # Preamble overrides are a separate feature; return empty strings so the
        # document is assembled from the content alone.
        main._preamble._preamble_heading_typst.return_value = ""
        return BulletinExporter(main)

    def test_leader_note_is_absent_from_the_whole_bulletin(self):
        exporter = self._exporter(_item_with_leader_note())
        self.assertNotIn("PRIVATE", exporter._build_bulletin_typst(digital=False))
        self.assertNotIn("PRIVATE", exporter._build_bulletin_html())

    def test_leader_note_is_present_in_the_manuscript(self):
        exporter = self._exporter(_item_with_leader_note())
        self.assertIn("PRIVATE", exporter._build_manuscript_typst())

    def test_stray_bracket_cannot_close_the_columns_block(self):
        """Bulletin content sits inside #columns(2)[…]; a bare ] would end it."""
        si = ServiceItem("Notices", "Gathering")
        si.set_plain_text("see the notice] board")
        typ = self._exporter(si)._build_bulletin_typst(digital=False)
        self.assertIn(r"notice\] board", typ)

    def test_email_in_content_is_escaped_in_the_bulletin(self):
        si = ServiceItem("Notices", "Gathering")
        si.set_plain_text("Write to office@church.ca")
        typ = self._exporter(si)._build_bulletin_typst(digital=False)
        self.assertIn(r"office\@church.ca", typ)

    def test_bulletin_html_escapes_markup_typed_by_the_user(self):
        """WebKit silently dropped <office@church.ca> as an unknown tag."""
        si = ServiceItem("Notices", "Gathering")
        si.set_plain_text("Contact <office@church.ca> & the <b>office</b>")
        html = self._exporter(si)._build_bulletin_html()
        self.assertIn("&lt;office@church.ca&gt;", html)
        self.assertIn("&lt;b&gt;office&lt;/b&gt;", html)
        self.assertNotIn("<b>office</b>", html)

    def test_bulletin_summary_is_escaped(self):
        si = ServiceItem("Offering", "Response")
        si.bulletin_summary = "Give at hope@church.ca"
        typ = self._exporter(si)._build_bulletin_typst(digital=False)
        self.assertIn(r"hope\@church.ca", typ)


if __name__ == "__main__":
    unittest.main()
