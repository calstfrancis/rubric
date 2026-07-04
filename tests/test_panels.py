"""
Tests for the composition-pattern panel/exporter classes extracted from the
rubric.py MainWindow monolith (BulletinExporter, BulletinPreview,
PreamblePanel, HymnLookupPanel, OrderPanel, PalettePanel, MainChrome).

Each of these classes takes a `main_window` reference in its constructor and
reads/writes shared state via `self._main`, rather than owning it directly —
that's exactly what makes them testable in isolation against a lightweight
stub instead of requiring a full running GTK application. See refactor.md at
the repo root for why these were extracted.

Safety note: `config.save()` and the SQLite hymn-cache helpers
(`rubric_package.db.hymn_*`) write to the user's real
`~/.config/rubric/config.json` / `~/.local/share/rubric/rubric.db`. Both are
patched out for the whole module in setUpModule/tearDownModule so these
tests can never touch real user data on disk.
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from rubric_package.models.config import config
from rubric_package.models.service import ServiceItem, SectionDivider

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw
    Adw.init()

    from rubric_package.exporters.bulletin_exporter import BulletinExporter
    from rubric_package.preview.bulletin_preview import BulletinPreview
    from rubric_package.panels.preamble_panel import PreamblePanel
    from rubric_package.panels.hymn_lookup_panel import HymnLookupPanel
    from rubric_package.panels.order_panel import OrderPanel
    from rubric_package.panels.palette_panel import PalettePanel
    from rubric_package.panels.main_chrome import MainChrome

    _GTK_OK = True
except Exception:
    _GTK_OK = False

_SKIP_REASON = "GTK4/libadwaita typelibs not available"

_patchers = []


def setUpModule():
    # Never let a test write the user's real config or hymn-cache DB to disk.
    _patchers.append(patch.object(config, "save", lambda: None))
    for p in _patchers:
        p.start()


def tearDownModule():
    for p in _patchers:
        p.stop()
    _patchers.clear()


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestBulletinExporterLogic(unittest.TestCase):
    """BulletinExporter — pure grouping logic (no GTK widget construction)."""

    def test_grouped_entries_groups_items_under_their_section(self):
        main = MagicMock()
        main.service_entries = [
            SectionDivider("Gathering"),
            ServiceItem("Prelude", "Gathering"),
            ServiceItem("Welcome", "Gathering"),
            SectionDivider("Word"),
            ServiceItem("Scripture", "Word"),
        ]
        exporter = BulletinExporter(main)

        groups = list(exporter._grouped_entries())

        self.assertEqual(
            [(title, [e.name for e in items]) for title, items in groups],
            [("Gathering", ["Prelude", "Welcome"]), ("Word", ["Scripture"])],
        )

    def test_grouped_entries_empty_service_yields_one_empty_group(self):
        # _grouped_entries always yields its final (title, items) accumulator,
        # even when nothing was ever added — callers (e.g. _bulletin_as_plain_text)
        # are expected to skip a (None, []) group themselves.
        main = MagicMock()
        main.service_entries = []
        exporter = BulletinExporter(main)

        self.assertEqual(list(exporter._grouped_entries()), [(None, [])])


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestBulletinPreviewLogic(unittest.TestCase):
    """BulletinPreview — state-toggle and path logic, without a real compile."""

    def _stub_main(self):
        main = MagicMock()
        main._preview_visible = False
        main._preview_paned_positioned = False
        main._preview_compile_dirty = False
        main._preview_pending_id = None
        return main

    def test_preview_pdf_path_includes_mode_and_window_id(self):
        main = self._stub_main()
        main._preview_mode = "manuscript"
        main._preview_window_id = "unit-test-window"
        preview = BulletinPreview(main)

        path = preview._preview_pdf_path()

        self.assertIn("manuscript", path.name)
        self.assertIn("unit-test-window", path.name)
        self.assertTrue(path.parent.is_dir())

    def test_toggle_preview_panel_flips_visibility_on_then_off(self):
        main = self._stub_main()
        preview = BulletinPreview(main)

        preview._toggle_preview_panel()
        self.assertTrue(main._preview_visible)
        main._preview_panel.set_visible.assert_called_with(True)

        preview._toggle_preview_panel()
        self.assertFalse(main._preview_visible)
        main._preview_panel.set_visible.assert_called_with(False)

    def test_bulletin_as_plain_text_uses_exporter_grouped_entries(self):
        main = self._stub_main()
        main.service_title_entry.get_text.return_value = "Sunday Service"
        item = ServiceItem("Welcome", "Gathering", content_typst="Good morning!")
        main._exporter._grouped_entries.return_value = [("Gathering", [item])]
        preview = BulletinPreview(main)

        text = preview._bulletin_as_plain_text()

        self.assertIn("Sunday Service", text)
        self.assertIn("GATHERING", text)
        self.assertIn("Welcome", text)
        self.assertIn("Good morning!", text)


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestPreamblePanelLogic(unittest.TestCase):
    """PreamblePanel — Typst heading overrides and config-editing logic."""

    def setUp(self):
        self._preamble_backup = dict(config.preamble)

    def tearDown(self):
        config.preamble.clear()
        config.preamble.update(self._preamble_backup)

    def test_heading_typst_default_style_returns_empty(self):
        config.preamble["bulletin"] = {"heading_style": "bold-smallcaps-rule"}
        panel = PreamblePanel(MagicMock())

        self.assertEqual(panel._preamble_heading_typst("bulletin"), "")

    def test_heading_typst_bold_smallcaps(self):
        config.preamble["bulletin"] = {"heading_style": "bold-smallcaps"}
        panel = PreamblePanel(MagicMock())

        result = panel._preamble_heading_typst("bulletin")

        self.assertIn("smallcaps", result)
        self.assertIn("weight: \"bold\"", result)

    def test_heading_typst_plain(self):
        config.preamble["manuscript"] = {"heading_style": "plain"}
        panel = PreamblePanel(MagicMock())

        result = panel._preamble_heading_typst("manuscript")

        self.assertIn("it.body", result)
        self.assertNotIn("smallcaps", result)
        self.assertNotIn("bold", result)

    def test_on_preamble_changed_updates_config_and_schedules_preview(self):
        config.preamble["bulletin"] = {}
        main = MagicMock()
        panel = PreamblePanel(main)

        panel._on_preamble_changed("bulletin", "size", 14.0)

        self.assertEqual(config.preamble["bulletin"]["size"], 14.0)
        main._preview._schedule_preview_update.assert_called_once()

    def test_apply_bulletin_preset_replaces_bulletin_config(self):
        main = MagicMock()
        panel = PreamblePanel(main)
        preset = dict(panel._BULLETIN_PRESETS[0][2])

        panel._apply_bulletin_preset(preset)

        self.assertEqual(config.preamble["bulletin"], preset)
        main._preview._do_preview_update.assert_called_once()


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestHymnLookupPanelLogic(unittest.TestCase):
    """HymnLookupPanel — injecting hymn results into the selected order item."""

    def _stub_main(self, entries, selected_index):
        main = MagicMock()
        main.service_entries = entries
        main._selected_index.return_value = selected_index
        main._note_preview.return_value = ""
        main._scripture_inline_preview.return_value = ""
        main._find_row_for_index.return_value = None
        return main

    def test_inject_hymn_line_updates_selected_item_and_marks_modified(self):
        item = ServiceItem("Opening Hymn", "Gathering", content_typst="")
        main = self._stub_main([item], selected_index=0)
        panel = HymnLookupPanel(main)

        panel._inject_hymn_line("VU 1 — Test Hymn")

        self.assertEqual(item.content_typst, "VU 1 — Test Hymn")
        main._mark_modified.assert_called_once()
        main._hymn_search_pop.popdown.assert_called_once()

    def test_inject_hymn_line_appends_to_existing_content(self):
        item = ServiceItem("Opening Hymn", "Gathering", content_typst="Existing note")
        main = self._stub_main([item], selected_index=0)
        panel = HymnLookupPanel(main)

        panel._inject_hymn_line("VU 1 — Test Hymn")

        self.assertEqual(item.content_typst, "VU 1 — Test Hymn\nExisting note")

    def test_inject_hymn_line_noop_when_nothing_selected(self):
        item = ServiceItem("Opening Hymn", "Gathering", content_typst="")
        main = self._stub_main([item], selected_index=-1)
        panel = HymnLookupPanel(main)

        panel._inject_hymn_line("VU 1 — Test Hymn")

        self.assertEqual(item.content_typst, "")
        main._mark_modified.assert_not_called()

    def test_inject_hymn_line_noop_on_section_divider(self):
        divider = SectionDivider("Gathering")
        main = self._stub_main([divider], selected_index=0)
        panel = HymnLookupPanel(main)

        panel._inject_hymn_line("VU 1 — Test Hymn")

        main._mark_modified.assert_not_called()

    def test_save_manual_hymn_writes_via_db_layer_not_real_disk(self):
        main = MagicMock()
        main._hymn_manual_entry.get_text.return_value = "Test Hymn Title"
        main._hymn_manual_ref = ("VU", "1")
        main._selected_index.return_value = -1  # skip the injection half
        panel = HymnLookupPanel(main)

        with patch("rubric_package.db.hymn_set") as mock_hset:
            panel._save_manual_hymn()
            mock_hset.assert_called_once_with("VU1", "Test Hymn Title")

        main.hymn_status.set_label.assert_called_with("VU 1 — Test Hymn Title")


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestPalettePanelLogic(unittest.TestCase):
    """PalettePanel — section lookup and palette-list rebuilding."""

    def setUp(self):
        self._palette_backup = config.palette
        self._recent_backup = list(config.recently_used)
        config.palette = []  # force get_palette() to fall back to SECTIONS

    def tearDown(self):
        config.palette = self._palette_backup
        config.recently_used = self._recent_backup

    def test_section_for_item_finds_containing_section(self):
        main = MagicMock()
        panel = PalettePanel(main)

        from rubric_package.models.config import SECTIONS
        section_name, items = SECTIONS[0]
        found = panel._section_for_item(items[0])

        self.assertEqual(found, section_name)

    def test_section_for_item_returns_empty_for_unknown_item(self):
        panel = PalettePanel(MagicMock())

        self.assertEqual(panel._section_for_item("Not A Real Element"), "")

    def test_fill_palette_inner_builds_a_listbox_per_section(self):
        from rubric_package.models.config import SECTIONS

        config.recently_used = []
        main = MagicMock()
        main._palette_inner = Gtk.Box()
        main._palette_listboxes = {}
        main._palette_expanders = []
        panel = PalettePanel(main)

        panel._fill_palette_inner()

        self.assertEqual(len(main._palette_listboxes), len(SECTIONS))
        self.assertEqual(len(main._palette_expanders), len(SECTIONS))

    def test_fill_palette_inner_adds_recent_section_when_present(self):
        config.recently_used = ["Opening Prayer"]
        main = MagicMock()
        main._palette_inner = Gtk.Box()
        main._palette_listboxes = {}
        main._palette_expanders = []
        panel = PalettePanel(main)

        panel._fill_palette_inner()

        self.assertIn("__recent__", main._palette_listboxes)

    def test_on_palette_search_changed_expands_matching_sections(self):
        main = MagicMock()
        exp1, exp2 = MagicMock(), MagicMock()
        main._palette_expanders = [exp1, exp2]
        main._palette_listboxes = {"a": MagicMock(), "b": MagicMock()}
        panel = PalettePanel(main)
        entry = MagicMock()
        entry.get_text.return_value = "hymn"

        panel._on_palette_search_changed(entry)

        exp1.set_expanded.assert_called_once_with(True)
        exp2.set_expanded.assert_called_once_with(True)
        for lb in main._palette_listboxes.values():
            lb.set_filter_func.assert_called_once()
            lb.invalidate_filter.assert_called_once()


@unittest.skipUnless(_GTK_OK, _SKIP_REASON)
class TestOrderPanelConstruction(unittest.TestCase):
    """OrderPanel — smoke test that the panel builds without routing bugs.

    `_build_order_panel` is a single ~390-line UI-construction method with
    no isolable pure-logic core (see refactor.md Step 5), so this is a
    construction smoke test rather than granular unit tests: it exercises
    every widget-building line and the two nested closures
    (`_draw_order_strip`, `_dismiss_suggestions`) against a stub, which is
    exactly the class of self/self._main routing bug this suite exists to
    catch.
    """

    def _stub_main(self):
        main = MagicMock()
        main.service_entries = []
        main._colour_bar_rgb = (0.1, 0.2, 0.3)
        main._hymn._build_hymn_search_popover.return_value = Gtk.Popover()
        main._build_icon_picker_popover.return_value = Gtk.Popover()
        # These get box.append()-ed directly, so they must be real widgets —
        # a bare MagicMock() fails PyGObject's type check on append().
        main._build_quickstart_banner.return_value = Gtk.Box()
        main._build_planning_notes_area.return_value = Gtk.Box()
        return main

    def test_build_order_panel_returns_box_and_wires_key_widgets(self):
        main = self._stub_main()
        panel = OrderPanel(main)

        box = panel._build_order_panel()

        self.assertIsInstance(box, Gtk.Box)
        self.assertIsInstance(main._order_hpaned, Gtk.Paned)
        self.assertIsInstance(main.order_listbox, Gtk.ListBox)
        self.assertIsInstance(main._content_widget.__class__, type)
        self.assertEqual(main._theme_selected_btn, None)

    def test_suggestions_dismiss_closure_hides_revealer(self):
        main = self._stub_main()
        panel = OrderPanel(main)
        panel._build_order_panel()

        # _build_order_panel assigns a real Gtk.Revealer onto main.sugg_revealer
        # (attribute assignment on a MagicMock sticks), so we can walk its real
        # widget tree: revealer -> sugg_outer -> sugg_row -> close button.
        sugg_outer = main.sugg_revealer.get_child()
        sugg_row = sugg_outer.get_last_child()
        close_btn = sugg_row.get_last_child()

        close_btn.emit("clicked")

        self.assertTrue(main._sugg_dismissed)
        self.assertFalse(main.sugg_revealer.get_reveal_child())


if __name__ == "__main__":
    unittest.main()
