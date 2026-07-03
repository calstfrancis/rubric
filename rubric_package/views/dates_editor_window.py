"""DatesEditorWindow — editable spreadsheet over config.all_dates (custom observances)."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from rubric_package.models.config import config, seed_all_dates


class DatesEditorWindow(Adw.Window):
    """Single editable spreadsheet over config.all_dates."""

    # All observance types — order matters (matches dropdown index)
    _TYPE_KEYS = ["social_justice", "indigenous", "ecological", "pride",
                  "feast", "saint", "ecumenical", "remembrance", "civil", "ucc"]
    _TYPE_LBLS = ["Justice / Social", "Indigenous", "Ecological", "Pride",
                  "Feast Day", "Saint", "Ecumenical", "Remembrance", "Civil", "UCC"]
    _MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]

    def __init__(self, main_win=None, **kw):
        super().__init__(**kw)
        self._main = main_win
        self.set_title("Important Dates")
        self.set_default_size(700, 640)
        self._sheet_box = None
        self._build()

    _SHEET_CSS = b"""
.dates-sheet-header { font-weight: bold; font-size: 0.8em; color: alpha(currentColor, 0.55); }
.dates-sheet-row { border-bottom: 1px solid alpha(currentColor, 0.08); }
.dates-sheet-row:last-child { border-bottom: none; }
.dates-cell-day   { min-width: 44px;  max-width: 44px; }
.dates-cell-month { min-width: 60px;  max-width: 60px; }
.dates-cell-type  { min-width: 150px; max-width: 150px; }
.dates-cell-del   { min-width: 36px;  max-width: 36px; }
"""

    def _build(self):
        css = Gtk.CssProvider()
        css.load_from_data(self._SHEET_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()

        reset_btn = Gtk.Button(label="Reset to defaults")
        reset_btn.add_css_class("flat")
        reset_btn.set_tooltip_text(
            "Restore all built-in observances — adds any missing defaults back. "
            "Your edits are replaced by the original values.")
        reset_btn.connect("clicked", self._on_reset)
        hdr.pack_end(reset_btn)

        tv.add_top_bar(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self._sheet_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._sheet_box.set_margin_start(10); self._sheet_box.set_margin_end(10)
        self._sheet_box.set_margin_top(6); self._sheet_box.set_margin_bottom(10)
        scroll.set_child(self._sheet_box)

        tv.set_content(scroll)
        self.set_content(tv)
        self._rebuild_sheet()

    def _notify_main(self):
        if self._main and hasattr(self._main, "_refresh_justice_row"):
            d = getattr(self._main, "selected_date", None)
            if d:
                self._main._refresh_justice_row(d)

    def _col_header_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row.set_margin_start(6); row.set_margin_end(6)
        row.set_margin_top(4); row.set_margin_bottom(4)
        for text, css_class, expand in [
            ("Mo",    "dates-cell-month", False),
            ("Day",   "dates-cell-day",   False),
            ("Name",  None,               True),
            ("Type",  "dates-cell-type",  False),
            ("",      "dates-cell-del",   False),
        ]:
            lbl = Gtk.Label(label=text)
            lbl.add_css_class("dates-sheet-header")
            lbl.set_xalign(0)
            if css_class:
                lbl.add_css_class(css_class)
            if expand:
                lbl.set_hexpand(True)
            row.append(lbl)
        return row

    def _data_row(self, idx: int) -> Gtk.Box:
        """One editable spreadsheet row for config.all_dates[idx]."""
        entry = config.all_dates[idx]

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row.add_css_class("dates-sheet-row")
        row.set_margin_start(6); row.set_margin_end(6)
        row.set_margin_top(1); row.set_margin_bottom(1)

        def _save():
            config.save()
            self._notify_main()

        month_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        month_spin.set_value(entry.get("month", 1))
        month_spin.set_width_chars(2)
        month_spin.add_css_class("dates-cell-month")
        month_spin.set_valign(Gtk.Align.CENTER)
        month_spin.connect("value-changed",
            lambda w, i=idx: (config.all_dates[i].__setitem__("month", int(w.get_value())), _save()))
        row.append(month_spin)

        day_spin = Gtk.SpinButton.new_with_range(1, 31, 1)
        day_spin.set_value(entry.get("day", 1))
        day_spin.set_width_chars(2)
        day_spin.add_css_class("dates-cell-day")
        day_spin.set_valign(Gtk.Align.CENTER)
        day_spin.connect("value-changed",
            lambda w, i=idx: (config.all_dates[i].__setitem__("day", int(w.get_value())), _save()))
        row.append(day_spin)

        name_entry = Gtk.Entry()
        name_entry.set_text(entry.get("name", ""))
        name_entry.set_hexpand(True)
        name_entry.set_valign(Gtk.Align.CENTER)
        def _on_name(w, i=idx):
            config.all_dates[i]["name"] = w.get_text()
            _save()
        name_entry.connect("changed", _on_name)
        row.append(name_entry)

        type_dd = Gtk.DropDown.new_from_strings(self._TYPE_LBLS)
        type_dd.add_css_class("dates-cell-type")
        type_dd.set_valign(Gtk.Align.CENTER)
        cur_type = entry.get("type", "social_justice")
        if cur_type in self._TYPE_KEYS:
            type_dd.set_selected(self._TYPE_KEYS.index(cur_type))
        def _on_type(w, _prop, i=idx):
            sel = w.get_selected()
            config.all_dates[i]["type"] = (
                self._TYPE_KEYS[sel] if sel < len(self._TYPE_KEYS) else "social_justice")
            _save()
        type_dd.connect("notify::selected", _on_type)
        row.append(type_dd)

        del_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Delete row")
        del_btn.add_css_class("flat")
        del_btn.add_css_class("dates-cell-del")
        del_btn.set_valign(Gtk.Align.CENTER)
        def _on_del(_b, i=idx):
            config.all_dates.pop(i)
            config.save()
            self._notify_main()
            self._rebuild_sheet()
        del_btn.connect("clicked", _on_del)
        row.append(del_btn)

        return row

    def _add_row_widget(self) -> Gtk.Box:
        """Blank bottom row for appending a new entry."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row.set_margin_start(6); row.set_margin_end(6)
        row.set_margin_top(4); row.set_margin_bottom(4)

        month_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        month_spin.set_width_chars(2)
        month_spin.add_css_class("dates-cell-month")
        month_spin.set_valign(Gtk.Align.CENTER)
        row.append(month_spin)

        day_spin = Gtk.SpinButton.new_with_range(1, 31, 1)
        day_spin.set_width_chars(2)
        day_spin.add_css_class("dates-cell-day")
        day_spin.set_valign(Gtk.Align.CENTER)
        row.append(day_spin)

        name_entry = Gtk.Entry()
        name_entry.set_hexpand(True)
        name_entry.set_valign(Gtk.Align.CENTER)
        name_entry.set_placeholder_text("New observance name…")
        row.append(name_entry)

        type_dd = Gtk.DropDown.new_from_strings(self._TYPE_LBLS)
        type_dd.add_css_class("dates-cell-type")
        type_dd.set_valign(Gtk.Align.CENTER)
        row.append(type_dd)

        add_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add row")
        add_btn.add_css_class("flat")
        add_btn.add_css_class("dates-cell-del")
        add_btn.set_valign(Gtk.Align.CENTER)

        def _on_add(_b):
            name = name_entry.get_text().strip()
            if not name:
                return
            sel = type_dd.get_selected()
            t = self._TYPE_KEYS[sel] if sel < len(self._TYPE_KEYS) else "social_justice"
            config.all_dates.append({
                "month": int(month_spin.get_value()),
                "day":   int(day_spin.get_value()),
                "name":  name,
                "type":  t,
            })
            config.save()
            self._notify_main()
            self._rebuild_sheet()

        add_btn.connect("clicked", _on_add)
        name_entry.connect("activate", _on_add)
        row.append(add_btn)
        return row

    def _rebuild_sheet(self):
        box = self._sheet_box
        while box.get_first_child():
            box.remove(box.get_first_child())

        box.append(self._col_header_row())
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        for i in range(len(config.all_dates)):
            box.append(self._data_row(i))

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        box.append(sep)
        box.append(self._add_row_widget())

    def _on_reset(self, _btn):
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading="Reset to defaults?",
            body="This will replace all dates with the built-in observances from observances.py. "
                 "Any edits you've made (including deleted or renamed dates) will be lost.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("reset",  "Reset")
        dlg.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        def _on_response(_d, resp):
            if resp == "reset":
                config.all_dates.clear()
                seed_all_dates()
                self._rebuild_sheet()
                self._notify_main()
        dlg.connect("response", _on_response)
        dlg.present()
