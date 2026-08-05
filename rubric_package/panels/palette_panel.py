"""PalettePanel — the element palette sidebar for Rubric.

Owns the searchable palette of insertable service elements (recently-used
list, per-section expanders, hymn cache indicator/clear button) shown in the
left sidebar. Constructed with a reference to the MainWindow instance it
serves, the same composition pattern used by BulletinExporter, BulletinPreview,
PreamblePanel, HymnLookupPanel, OrderPanel, and MainChrome.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Pango

from rubric_package.models.config import config, get_palette


def _rows(listbox):
    i = 0
    while True:
        r = listbox.get_row_at_index(i)
        if r is None:
            return
        yield r
        i += 1


class PalettePanel:
    """Owns the searchable element-palette sidebar."""

    def __init__(self, main_window):
        self._main = main_window

    def _build_palette_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); box.set_size_request(230,-1)
        # Search entry
        self._main._palette_search = Gtk.SearchEntry()
        self._main._palette_search.set_placeholder_text("Search elements…")
        self._main._palette_search.set_margin_start(12); self._main._palette_search.set_margin_end(12)
        self._main._palette_search.set_margin_top(6); self._main._palette_search.set_margin_bottom(2)
        self._main._palette_search.add_css_class("fond-search")
        self._main._palette_search.connect("search-changed", self._on_palette_search_changed)
        box.append(self._main._palette_search)

        # The hymn-cache readout and its Clear button moved to Preferences —
        # it's a maintenance statistic, not something to keep on screen.

        box.add_css_class("fond-sidebar")
        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); scroll.set_vexpand(True)
        self._main._palette_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main._palette_inner.set_margin_top(4); self._main._palette_inner.set_margin_bottom(8)
        self._main._palette_listboxes: dict[str,Gtk.ListBox] = {}
        self._main._palette_expanders: list[Gtk.Expander] = []
        self._fill_palette_inner()
        scroll.set_child(self._main._palette_inner); box.append(scroll)
        return box

    def hymn_cache_count(self) -> int:
        try:
            from rubric_package.db import hymn_count as _hcount
            return _hcount()
        except Exception:
            return 0

    def _on_hymn_cache_clear(self, _btn=None) -> int:
        """Empty the hymn cache and report what it holds afterwards.

        Called from Preferences now rather than from a row above the palette.
        """
        try:
            from rubric_package.db import hymn_clear
            hymn_clear()
        except Exception:
            pass
        return self.hymn_cache_count()

    def _on_palette_search_changed(self, entry):
        text = entry.get_text().lower().strip()
        if text:
            for exp in self._main._palette_expanders:
                exp.set_expanded(True)
        for lb in self._main._palette_listboxes.values():
            if text:
                lb.set_filter_func(
                    lambda row, t=text: hasattr(row, '_item_name') and t in row._item_name.lower())
            else:
                lb.set_filter_func(None)
            lb.invalidate_filter()

    def _section_for_item(self, name: str) -> str:
        for sname, items in get_palette():
            if name in items:
                return sname
        return ""

    def _make_palette_row(self, name: str, section: str) -> Gtk.ListBoxRow:
        """One element in the palette, styled as the order list's rows are."""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.add_css_class("fond-card"); row.add_css_class("fond-row")
        row._item_name = name
        row._section_name = section
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bx.set_margin_start(12); bx.set_margin_end(10)
        lbl = Gtk.Label(label=name)
        lbl.add_css_class("fond-row-title")
        lbl.set_xalign(0)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        bx.append(lbl)
        row.set_child(bx)
        return row

    def _make_palette_header(self, title: str, section: str | None) -> Gtk.Widget:
        """The same section header the service order uses: dot, small caps."""
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bx.add_css_class("fond-section")
        if section is not None:
            dot = Gtk.Label(label="\u25cf")
            dot.add_css_class("fond-section-dot")
            dot.add_css_class(self._main._section_dot_class(section))
            dot.set_valign(Gtk.Align.CENTER)
            bx.append(dot)
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("fond-section-title")
        lbl.set_valign(Gtk.Align.CENTER)
        bx.append(lbl)
        return bx

    def _make_palette_list(self, items, section: str) -> Gtk.ListBox:
        lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
        lb.add_css_class("fond-list"); lb.add_css_class("palette-list")
        lb.set_valign(Gtk.Align.START)
        lb.connect("row-activated", self._main._on_palette_row_activated)
        for pos, name in enumerate(items):
            row = self._make_palette_row(name, section)
            if pos == 0: row.add_css_class("fond-card-first")
            if pos == len(items) - 1: row.add_css_class("fond-card-last")
            lb.append(row)
        return lb

    def _fill_palette_inner(self):
        while True:
            c = self._main._palette_inner.get_first_child()
            if c is None: break
            self._main._palette_inner.remove(c)
        self._main._palette_listboxes.clear()
        self._main._palette_expanders.clear()

        # Recently used
        if config.recently_used:
            hdr = self._make_palette_header("Recent", None)
            hdr.set_margin_start(16); hdr.set_margin_end(16)
            hdr.set_margin_top(8); hdr.set_margin_bottom(2)
            self._main._palette_inner.append(hdr)
            recent = list(config.recently_used[:6])
            rec_lb = self._make_palette_list(recent, "")
            for row in _rows(rec_lb):
                row._section_name = self._section_for_item(row._item_name)
            rec_lb.set_margin_start(16); rec_lb.set_margin_end(16); rec_lb.set_margin_bottom(6)
            self._main._palette_inner.append(rec_lb)
            self._main._palette_listboxes["__recent__"] = rec_lb

        # Sections. Still collapsible — fifty elements need it — but the
        # disclosure carries the order list's section header rather than
        # GTK's default expander label.
        for i, (sname, items) in enumerate(get_palette()):
            exp = Gtk.Expander()
            exp.set_label_widget(self._make_palette_header(sname, sname))
            exp.add_css_class("palette-section")
            exp.set_margin_start(16); exp.set_margin_end(16)
            exp.set_margin_top(8); exp.set_margin_bottom(2)
            exp.set_expanded(i == 0)
            lb = self._make_palette_list(items, sname)
            lb.set_margin_top(4); lb.set_margin_bottom(4)
            exp.set_child(lb)
            self._main._palette_inner.append(exp)
            self._main._palette_listboxes[sname] = lb
            self._main._palette_expanders.append(exp)

    def _refresh_recently_used(self):
        lb = self._main._palette_listboxes.get("__recent__")
        if lb is None:
            self._fill_palette_inner(); return
        while lb.get_first_child():
            lb.remove(lb.get_first_child())
        for rname in config.recently_used[:6]:
            row = Adw.ActionRow(title=GLib.markup_escape_text(rname)); row.set_activatable(True)
            row._item_name = rname; row._section_name = self._section_for_item(rname)
            lb.append(row)
