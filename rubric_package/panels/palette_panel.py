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
        # Search entry, with the "new element" button beside it
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        search_row.set_margin_start(12); search_row.set_margin_end(12)
        search_row.set_margin_top(6); search_row.set_margin_bottom(2)
        self._main._palette_search = Gtk.SearchEntry()
        self._main._palette_search.set_placeholder_text("Search elements…")
        self._main._palette_search.set_hexpand(True)
        self._main._palette_search.add_css_class("fond-search")
        self._main._palette_search.connect("search-changed", self._on_palette_search_changed)
        search_row.append(self._main._palette_search)
        new_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_btn.set_tooltip_text("New element — add one to the palette")
        new_btn.add_css_class("flat")
        new_btn.set_valign(Gtk.Align.CENTER)
        new_btn.connect("clicked", self._on_new_element_clicked)
        search_row.append(new_btn)
        box.append(search_row)

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

    # ── Creating new elements ─────────────────────────────────────────────────

    def add_element(self, name: str, section: str) -> bool:
        """Add `name` to `section` in the saved palette. False if it's a duplicate.

        The palette lives in config only once it's been customised (get_palette()
        falls back to the built-in SECTIONS), so the first custom element has to
        materialise the current palette into config.palette before appending.
        """
        name = name.strip()
        if not name:
            return False
        if any(name.lower() == existing.lower()
               for _s, items in get_palette() for existing in items):
            return False
        if not config.palette:
            config.palette = [{"section": s, "items": list(i)} for s, i in get_palette()]
        for sd in config.palette:
            if sd["section"] == section:
                sd["items"].append(name)
                break
        else:
            config.palette.append({"section": section, "items": [name]})
        config.save()
        return True

    def _expanded_section(self) -> str | None:
        """The section the user is currently looking at, if any is open."""
        for exp, (sname, _items) in zip(self._main._palette_expanders, get_palette()):
            if exp.get_expanded():
                return sname
        return None

    def _on_new_element_clicked(self, _btn=None):
        sections = [s for s, _ in get_palette()]
        if not sections:
            return

        win = Adw.Window(transient_for=self._main, modal=True)
        win.set_title("New element")
        win.set_default_size(360, -1)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12); outer.set_margin_bottom(12)
        outer.set_margin_start(16); outer.set_margin_end(16)

        grp = Adw.PreferencesGroup()
        grp.set_description("Elements added here stay in the palette for every service.")
        name_row = Adw.EntryRow(title="Element name")
        grp.add(name_row)
        section_row = Adw.ComboRow(title="Section")
        section_row.set_model(Gtk.StringList.new(sections))
        current = self._expanded_section()
        if current in sections:
            section_row.set_selected(sections.index(current))
        grp.add(section_row)
        outer.append(grp)

        err = Gtk.Label(label="", xalign=0)
        err.add_css_class("caption"); err.add_css_class("error")
        err.set_margin_top(6); err.set_visible(False)
        outer.append(err)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(16)
        sp = Gtk.Box(); sp.set_hexpand(True); btn_row.append(sp)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: win.close())
        btn_row.append(cancel_btn)
        add_btn = Gtk.Button(label="Add")
        add_btn.add_css_class("suggested-action")

        def on_add(_b=None):
            nm = name_row.get_text().strip()
            if not nm:
                name_row.add_css_class("error")
                err.set_label("Give the element a name."); err.set_visible(True)
                return
            sec = sections[section_row.get_selected()]
            if not self.add_element(nm, sec):
                name_row.add_css_class("error")
                err.set_label(f"“{nm}” is already in the palette.")
                err.set_visible(True)
                return
            win.close()
            self._fill_palette_inner()
            self._reveal_section(sec)
            self._toast_added(nm, sec)

        def on_changed(_r):
            name_row.remove_css_class("error"); err.set_visible(False)

        name_row.connect("changed", on_changed)
        name_row.connect("entry-activated", on_add)
        add_btn.connect("clicked", on_add)
        btn_row.append(add_btn)
        outer.append(btn_row)

        tv.set_content(outer); win.set_content(tv); win.present()
        GLib.idle_add(name_row.grab_focus)

    def _reveal_section(self, section: str):
        """Open the expander holding `section` so the new element is visible."""
        for exp, (sname, _items) in zip(self._main._palette_expanders, get_palette()):
            exp.set_expanded(sname == section)

    def _toast_added(self, name: str, section: str):
        """Confirm the addition, offering to drop it into the open service too."""
        overlay = getattr(self._main, "_toast_overlay", None)
        if overlay is None:
            return
        toast = Adw.Toast.new(f'“{name}” added to {section}')
        toast.set_timeout(6)
        toast.set_button_label("Add to service")

        def on_add_to_service(_t):
            from rubric_package.models.service import ServiceItem
            self._main._push_undo()
            self._main._add_entry(ServiceItem(name, section))

        toast.connect("button-clicked", on_add_to_service)
        overlay.add_toast(toast)

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
