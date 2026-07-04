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
from gi.repository import Gtk, Adw, GLib

from rubric_package.models.config import config, get_palette


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
        self._main._palette_search.set_margin_top(8); self._main._palette_search.set_margin_bottom(2)
        self._main._palette_search.connect("search-changed", self._on_palette_search_changed)
        box.append(self._main._palette_search)

        # Hymn cache indicator
        cache_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        cache_bar.set_margin_start(12); cache_bar.set_margin_end(12)
        cache_bar.set_margin_bottom(4)
        try:
            from rubric_package.db import hymn_count as _hcount
            _n = _hcount()
        except Exception:
            _n = 0
        self._main._hymn_cache_lbl = Gtk.Label(label=f"📚 {_n} hymns cached")
        self._main._hymn_cache_lbl.add_css_class("caption")
        self._main._hymn_cache_lbl.add_css_class("dim-label")
        self._main._hymn_cache_lbl.set_hexpand(True); self._main._hymn_cache_lbl.set_xalign(0)
        cache_bar.append(self._main._hymn_cache_lbl)
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.add_css_class("flat"); clear_btn.add_css_class("caption")
        clear_btn.connect("clicked", self._on_hymn_cache_clear)
        cache_bar.append(clear_btn)
        box.append(cache_bar)

        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); scroll.set_vexpand(True)
        self._main._palette_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main._palette_inner.set_margin_top(4); self._main._palette_inner.set_margin_bottom(8)
        self._main._palette_listboxes: dict[str,Gtk.ListBox] = {}
        self._main._palette_expanders: list[Gtk.Expander] = []
        self._fill_palette_inner()
        scroll.set_child(self._main._palette_inner); box.append(scroll)
        return box

    def _on_hymn_cache_clear(self, _btn):
        try:
            from rubric_package.db import hymn_clear, hymn_count as _hcount
            hymn_clear()
            self._main._hymn_cache_lbl.set_label(f"📚 {_hcount()} hymns cached")
        except Exception:
            pass

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

    def _fill_palette_inner(self):
        while True:
            c = self._main._palette_inner.get_first_child()
            if c is None: break
            self._main._palette_inner.remove(c)
        self._main._palette_listboxes.clear()
        self._main._palette_expanders.clear()

        # Recently used section
        if config.recently_used:
            rec_lbl = Gtk.Label(label="Recent")
            rec_lbl.add_css_class("caption"); rec_lbl.add_css_class("dim-label")
            rec_lbl.set_xalign(0)
            rec_lbl.set_margin_start(12); rec_lbl.set_margin_end(12)
            rec_lbl.set_margin_top(8); rec_lbl.set_margin_bottom(2)
            self._main._palette_inner.append(rec_lbl)
            rec_lb = Gtk.ListBox(); rec_lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
            rec_lb.add_css_class("boxed-list")
            rec_lb.set_margin_start(12); rec_lb.set_margin_end(12); rec_lb.set_margin_bottom(4)
            rec_lb.connect("row-activated", self._main._on_palette_row_activated)
            for rname in config.recently_used[:6]:
                row = Adw.ActionRow(title=GLib.markup_escape_text(rname)); row.set_activatable(True)
                row._item_name = rname; row._section_name = self._section_for_item(rname)
                rec_lb.append(row)
            self._main._palette_inner.append(rec_lb)
            self._main._palette_listboxes["__recent__"] = rec_lb
            self._main._palette_inner.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Sections with expanders (first expanded, rest collapsed)
        for i, (sname, items) in enumerate(get_palette()):
            exp = Gtk.Expander(label=sname)
            exp.set_margin_start(12); exp.set_margin_end(12)
            exp.set_margin_top(8); exp.set_margin_bottom(2)
            exp.set_expanded(i == 0)
            lb = Gtk.ListBox(); lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
            lb.add_css_class("boxed-list"); lb.set_margin_bottom(4)
            lb.connect("row-activated", self._main._on_palette_row_activated)
            for iname in items:
                row = Adw.ActionRow(title=GLib.markup_escape_text(iname)); row.set_activatable(True)
                row._item_name = iname; row._section_name = sname; lb.append(row)
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
