"""PreamblePanel — document-template (font/margin/heading) editor for Rubric.

Owns the "Document Template" side panel: the manuscript/bulletin preset and
per-field editing UI, and the Typst heading-override helper that
BulletinExporter reads back when building documents. Constructed with a
reference to the MainWindow instance it serves, the same composition pattern
used by BulletinExporter and BulletinPreview.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from rubric_package.models.config import config


class PreamblePanel:
    """Owns the document-template editor panel UI and its preset/field logic."""

    _BULLETIN_PRESETS = [
        (
            "Classic",
            "Two columns · small-caps headings with rule · 11 pt\n"
            "Traditional, formal — suits most congregations",
            {
                "font": "", "size": 11.0,
                "margin_top": 0.65, "margin_bottom": 0.65,
                "margin_left": 0.6,  "margin_right": 0.6,
                "columns": 2, "heading_style": "bold-smallcaps-rule",
            },
        ),
        (
            "Contemporary",
            "Two columns · clean bold headings · 10.5 pt\n"
            "Modern, welcoming — less ornate than Classic",
            {
                "font": "", "size": 10.5,
                "margin_top": 0.55, "margin_bottom": 0.55,
                "margin_left": 0.5,  "margin_right": 0.5,
                "columns": 2, "heading_style": "bold",
            },
        ),
        (
            "Large Print",
            "Single column · bold small-caps headings · 14 pt\n"
            "Accessible — clear for low-vision readers",
            {
                "font": "", "size": 14.0,
                "margin_top": 0.6,  "margin_bottom": 0.6,
                "margin_left": 0.65, "margin_right": 0.65,
                "columns": 1, "heading_style": "bold-smallcaps",
            },
        ),
        (
            "Compact",
            "Two columns · plain headings · 9.5 pt · tight margins\n"
            "Fits long services on fewer pages",
            {
                "font": "", "size": 9.5,
                "margin_top": 0.5,  "margin_bottom": 0.5,
                "margin_left": 0.45, "margin_right": 0.45,
                "columns": 2, "heading_style": "plain",
            },
        ),
    ]

    def __init__(self, main_window):
        self._main = main_window

    def _preamble_heading_typst(self, key: str) -> str:
        """Return Typst #show heading override for the given template key, or '' for default."""
        style = config.preamble.get(key, {}).get("heading_style", "bold-smallcaps-rule")
        if style == "bold-smallcaps-rule":
            return ""  # Default — already in TYPST_SHARED
        if style == "bold-smallcaps":
            body = "text(weight: \"bold\", smallcaps(it.body))"
        elif style == "bold":
            body = "text(weight: \"bold\", it.body)"
        else:
            body = "it.body"
        return (
            "#show heading.where(level: 2): it => {\n"
            "  v(10pt)\n"
            f"  {body}\n"
            "  v(4pt, weak: true)\n"
            "}"
        )

    def _on_preamble_changed(self, key: str, field: str, value) -> None:
        if key not in config.preamble:
            config.preamble[key] = {}
        config.preamble[key][field] = value
        config.save()
        self._main._preview._schedule_preview_update()

    def _apply_bulletin_preset(self, preset: dict) -> None:
        config.preamble["bulletin"] = dict(preset)
        config.save()
        self._rebuild_preamble_form("bulletin")
        self._main._preview._do_preview_update()

    def _rebuild_preamble_form(self, key: str) -> None:
        old = self._main._preamble_form_stack.get_child_by_name(key)
        if old:
            self._main._preamble_form_stack.remove(old)
        new_form = self._build_preamble_form(key)
        self._main._preamble_form_stack.add_named(new_form, key)
        self._main._preamble_form_stack.set_visible_child_name(key)

    def _get_system_fonts(self) -> list[str]:
        # Ask Typst directly — it knows exactly which font families it can load.
        # Pango/fontconfig exposes variable-font axis values as separate family
        # names (e.g. "Crimson Pro ExtraBold") that Typst can't find by name,
        # so using the Pango list fills the picker with fonts that silently fall
        # back to the default when compiled.
        try:
            typst_bin = self._main._find_typst()
            if typst_bin:
                cmd = [typst_bin, "fonts"]
                for _fp in [
                    "/run/host/fonts",
                    "/run/host/usr/share/fonts",
                    "/usr/share/fonts",
                    "/usr/local/share/fonts",
                    str(Path.home() / ".fonts"),
                    str(Path.home() / ".local/share/fonts"),
                ]:
                    if Path(_fp).is_dir():
                        cmd += ["--font-path", _fp]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    names = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
                    return sorted(set(names))
        except Exception:
            pass
        # Fallback: Pango (some fonts will silently not render)
        try:
            from gi.repository import PangoCairo
            fm = PangoCairo.font_map_get_default()
            return sorted(f.get_name() for f in fm.list_families())
        except Exception:
            return []

    def _build_preamble_form(self, key: str) -> Gtk.Widget:
        """Scrollable preference form for manuscript or bulletin template settings."""
        _MS_DEF = {
            "font": "", "size": 11.0,
            "margin_top": 1.0, "margin_bottom": 1.0,
            "margin_left": 0.7, "margin_right": 0.7,
            "heading_style": "bold-smallcaps-rule",
            "columns": 2,
        }
        _BUL_DEF = {
            "font": "", "size": 11.0,
            "margin_top": 0.7, "margin_bottom": 0.7,
            "margin_left": 0.6, "margin_right": 0.6,
            "heading_style": "bold-smallcaps-rule",
            "columns": 2,
        }
        defaults = _MS_DEF if key == "manuscript" else _BUL_DEF
        p = config.preamble.get(key, {})

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        page = Adw.PreferencesPage()
        page.set_vexpand(True)

        # ── Style presets (bulletin only) ─────────────────────────────────────
        if key == "bulletin":
            preset_grp = Adw.PreferencesGroup(
                title="Style presets",
                description="Apply a starting point — you can fine-tune below")
            page.add(preset_grp)
            for p_name, p_desc, p_vals in self._BULLETIN_PRESETS:
                row = Adw.ActionRow(title=p_name, subtitle=p_desc.replace("\n", " · "))
                btn = Gtk.Button(label="Apply", valign=Gtk.Align.CENTER)
                btn.add_css_class("flat")
                btn.connect("clicked", lambda _b, v=p_vals: self._apply_bulletin_preset(v))
                row.add_suffix(btn)
                preset_grp.add(row)

        # ── Typography ────────────────────────────────────────────────────────
        typo_grp = Adw.PreferencesGroup(title="Typography")
        page.add(typo_grp)

        # Font family — dropdown of system fonts
        system_fonts = self._get_system_fonts()
        font_names = ["Default"] + system_fonts
        font_model = Gtk.StringList.new(font_names)
        font_row = Adw.ComboRow(title="Font family", model=font_model)
        font_row.set_enable_search(True)
        font_row.set_expression(
            Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        current_font = p.get("font", defaults["font"])
        try:
            font_row.set_selected(system_fonts.index(current_font) + 1 if current_font else 0)
        except ValueError:
            font_row.set_selected(0)

        def _on_font_selected(row, _prop):
            sel = row.get_selected()
            self._on_preamble_changed(key, "font", "" if sel == 0 else font_names[sel])

        font_row.connect("notify::selected", _on_font_selected)
        typo_grp.add(font_row)

        size_adj = Gtk.Adjustment(
            value=p.get("size", defaults["size"]),
            lower=6, upper=36, step_increment=0.5)
        size_row = Adw.SpinRow(adjustment=size_adj, digits=1, title="Font size (pt)")
        size_row.connect("notify::value",
                         lambda r, _p: self._on_preamble_changed(key, "size", r.get_value()))
        typo_grp.add(size_row)

        _spacing_def = 0.65
        spacing_adj = Gtk.Adjustment(
            value=p.get("par_spacing", _spacing_def),
            lower=0.0, upper=3.0, step_increment=0.05)
        spacing_row = Adw.SpinRow(adjustment=spacing_adj, digits=2,
                                   title="Paragraph spacing (em)",
                                   subtitle="Vertical space between paragraphs")
        spacing_row.connect("notify::value",
                            lambda r, _p: self._on_preamble_changed(key, "par_spacing", r.get_value()))
        typo_grp.add(spacing_row)

        # ── Margins ───────────────────────────────────────────────────────────
        margin_grp = Adw.PreferencesGroup(title="Margins (inches)")
        page.add(margin_grp)

        for field, label in (
            ("margin_top",    "Top"),
            ("margin_bottom", "Bottom"),
            ("margin_left",   "Left"),
            ("margin_right",  "Right"),
        ):
            adj = Gtk.Adjustment(
                value=p.get(field, defaults[field]),
                lower=0.0, upper=4.0, step_increment=0.05)
            row = Adw.SpinRow(adjustment=adj, digits=2, title=label)
            row.connect("notify::value",
                        lambda r, _p, f=field: self._on_preamble_changed(key, f, r.get_value()))
            margin_grp.add(row)

        # ── Layout ────────────────────────────────────────────────────────────
        layout_grp = Adw.PreferencesGroup(title="Layout")
        page.add(layout_grp)

        col_row = Adw.SwitchRow(title="Two-column layout",
                                subtitle="Service order flows in two columns per section")
        col_row.set_active(p.get("columns", defaults["columns"]) >= 2)
        col_row.connect("notify::active",
                        lambda r, _p: self._on_preamble_changed(
                            key, "columns", 2 if r.get_active() else 1))
        layout_grp.add(col_row)

        if key == "manuscript":
            hdr_row = Adw.SwitchRow(title="Compact title header",
                                    subtitle="Show church name, service title, and date at the top")
            hdr_row.set_active(p.get("show_header", True))
            hdr_row.connect("notify::active",
                            lambda r, _p: self._on_preamble_changed(
                                "manuscript", "show_header", r.get_active()))
            layout_grp.add(hdr_row)

        _gutter_def = 1.0 if key == "manuscript" else 0.5
        gutter_adj = Gtk.Adjustment(
            value=p.get("gutter", _gutter_def),
            lower=0.0, upper=5.0, step_increment=0.1)
        gutter_row = Adw.SpinRow(adjustment=gutter_adj, digits=1,
                                  title="Column gutter (em)",
                                  subtitle="Space between the two columns")
        gutter_row.connect("notify::value",
                           lambda r, _p: self._on_preamble_changed(key, "gutter", r.get_value()))
        layout_grp.add(gutter_row)

        # ── Headings ──────────────────────────────────────────────────────────
        hdg_grp = Adw.PreferencesGroup(title="Headings")
        page.add(hdg_grp)

        _HDG_LABELS = [
            "Bold small-caps + rule",
            "Bold small-caps",
            "Bold",
            "Plain",
        ]
        _HDG_KEYS = ["bold-smallcaps-rule", "bold-smallcaps", "bold", "plain"]
        hdg_model = Gtk.StringList.new(_HDG_LABELS)
        hdg_row = Adw.ComboRow(title="Element heading style", model=hdg_model)
        current_style = p.get("heading_style", defaults["heading_style"])
        try:
            hdg_row.set_selected(_HDG_KEYS.index(current_style))
        except ValueError:
            hdg_row.set_selected(0)

        def _on_hdg_selected(row, _prop):
            self._on_preamble_changed(key, "heading_style",
                                      _HDG_KEYS[row.get_selected()])

        hdg_row.connect("notify::selected", _on_hdg_selected)
        hdg_grp.add(hdg_row)

        scroll.set_child(page)
        return scroll

    def _build_preamble_panel(self) -> Gtk.Box:
        """Build the document template editor panel (font, margins, etc.)."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.set_margin_start(12); hdr.set_margin_end(12)
        hdr.set_margin_top(10); hdr.set_margin_bottom(8)

        hdr_lbl = Gtk.Label(label="Document Template")
        hdr_lbl.add_css_class("title-4")
        hdr_lbl.set_hexpand(True); hdr_lbl.set_xalign(0)
        hdr.append(hdr_lbl)

        self._main._preamble_ms_btn = Gtk.ToggleButton(label="Manuscript")
        self._main._preamble_ms_btn.set_active(True)
        self._main._preamble_ms_btn.add_css_class("flat")
        self._main._preamble_bul_btn = Gtk.ToggleButton(label="Bulletin")
        self._main._preamble_bul_btn.set_group(self._main._preamble_ms_btn)
        self._main._preamble_bul_btn.add_css_class("flat")
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toggle_box.add_css_class("linked")
        toggle_box.append(self._main._preamble_ms_btn)
        toggle_box.append(self._main._preamble_bul_btn)
        hdr.append(toggle_box)
        outer.append(hdr)
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._main._preamble_form_stack = Gtk.Stack()
        self._main._preamble_form_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._main._preamble_form_stack.set_transition_duration(100)
        self._main._preamble_form_stack.set_vexpand(True)
        self._main._preamble_form_stack.add_named(self._build_preamble_form("manuscript"), "manuscript")
        self._main._preamble_form_stack.add_named(self._build_preamble_form("bulletin"), "bulletin")
        outer.append(self._main._preamble_form_stack)

        def _on_type_toggled(btn):
            if btn.get_active():
                mode = "manuscript" if btn == self._main._preamble_ms_btn else "bulletin"
                self._main._preamble_form_stack.set_visible_child_name(mode)
                # Mirror in the preview so font/margin changes are immediately visible
                self._main._preview_mode = mode
                self._main._preview_scroll_y = 0
                if hasattr(self._main, "_preview_manuscript_btn"):
                    if mode == "manuscript":
                        self._main._preview_manuscript_btn.set_active(True)
                    else:
                        self._main._preview_bulletin_btn.set_active(True)
                self._main._preview._do_preview_update()

        self._main._preamble_ms_btn.connect("toggled", _on_type_toggled)
        self._main._preamble_bul_btn.connect("toggled", _on_type_toggled)

        return outer
