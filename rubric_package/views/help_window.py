"""HelpWindow — tabbed Help / FAQ / What's New / About window for Rubric."""

from __future__ import annotations

import re
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class HelpWindow(Adw.Window):
    """Tabbed help window — Help, FAQ, What's New, About."""

    _TAB_IDX = {"help": 0, "faq": 1, "changelog": 2, "about": 3}

    def __init__(self, main_window, app_version: str, start_tab: str = "help", **kw):
        super().__init__(title="Help — Rubric", default_width=720, default_height=620, **kw)
        self._main = main_window
        self._app_version = app_version
        self.set_modal(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        self._nb = Gtk.Notebook()
        self._nb.set_show_border(False); self._nb.set_vexpand(True)

        self._nb.append_page(self._doc_page(self._find_doc("HELP.md")),      Gtk.Label(label="Help"))
        self._nb.append_page(self._doc_page(self._find_doc("FAQ.md")),       Gtk.Label(label="FAQ"))
        self._nb.append_page(self._doc_page(self._find_doc("CHANGELOG.md")), Gtk.Label(label="What's New"))
        self._nb.append_page(self._about_page(),                        Gtk.Label(label="About"))
        self._nb.set_current_page(self._TAB_IDX.get(start_tab, 0))

        tv.set_content(self._nb)
        self.set_content(tv)

    def switch_tab(self, name: str):
        self._nb.set_current_page(self._TAB_IDX.get(name, 0))

    @staticmethod
    def _find_doc(name: str) -> Path | None:
        p = Path(__file__).resolve().parent.parent.parent / name
        if p.exists():
            return p
        try:
            import rubric_package as _rp
            p2 = Path(_rp.__file__).parent / "data" / name
            if p2.exists():
                return p2
        except ImportError:
            pass
        return None

    def _doc_page(self, path: Path | None) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        tv = Gtk.TextView(); tv.set_editable(False); tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_top_margin(16); tv.set_bottom_margin(16)
        tv.set_left_margin(20); tv.set_right_margin(20)
        buf = tv.get_buffer()
        buf.create_tag("h1", weight=700, scale=1.4, pixels_above_lines=12, pixels_below_lines=4)
        buf.create_tag("h2", weight=700, scale=1.15, pixels_above_lines=10, pixels_below_lines=2)
        buf.create_tag("h3", weight=700, scale=1.0,  pixels_above_lines=8,  pixels_below_lines=2)
        buf.create_tag("bold",   weight=700)
        buf.create_tag("code",   family="monospace", background="#f0f0f0")
        buf.create_tag("hr",     strikethrough=True, foreground="#888888")
        buf.create_tag("bullet", left_margin=24)
        if path is None or not path.exists():
            buf.set_text("Documentation not found.", -1)
            scroll.set_child(tv); return scroll
        it = buf.get_end_iter(); in_code = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            if line.startswith("```"):
                in_code = not in_code; buf.insert(it, "\n"); continue
            if in_code:
                buf.insert_with_tags_by_name(it, line + "\n", "code"); continue
            if re.match(r'^---+$', line):
                buf.insert_with_tags_by_name(it, "─" * 40 + "\n", "hr"); continue
            m = re.match(r'^(#{1,3})\s+(.*)', line)
            if m:
                buf.insert_with_tags_by_name(it, m.group(2) + "\n", ["h1","h2","h3"][min(len(m.group(1))-1,2)]); continue
            m = re.match(r'^[-*]\s+(.*)', line)
            if m:
                buf.insert_with_tags_by_name(it, "  • " + m.group(1) + "\n", "bullet"); continue
            if re.match(r'^\|[-| :]+\|$', line): continue
            if line.startswith("|"):
                buf.insert_with_tags_by_name(it, line + "\n", "code"); continue
            if not line: buf.insert(it, "\n"); continue
            for part in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', line):
                if part.startswith("**") and part.endswith("**"):
                    buf.insert_with_tags_by_name(it, part[2:-2], "bold")
                elif part.startswith("`") and part.endswith("`"):
                    buf.insert_with_tags_by_name(it, part[1:-1], "code")
                else:
                    buf.insert(it, part)
            buf.insert(it, "\n")
        scroll.set_child(tv)
        return scroll

    def _about_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(40); box.set_margin_bottom(40)
        box.set_margin_start(40); box.set_margin_end(40)
        box.set_valign(Gtk.Align.CENTER)
        icon = Gtk.Image(icon_name="io.github.calstfrancis.rubric"); icon.set_pixel_size(64)
        box.append(icon)
        box.append(Gtk.Label(label="Rubric", css_classes=["title-1"]))
        box.append(Gtk.Label(label=f"Version {self._app_version}", css_classes=["dim-label"]))
        box.append(Gtk.Label(label="Worship service planning for United Church of Canada ministry",
                             css_classes=["body"]))
        box.append(Gtk.Label(label="© Cal St Francis · GPL-3.0",
                             css_classes=["caption", "dim-label"]))
        gh_btn = Gtk.Button(label="GitHub — calstfrancis/rubric")
        gh_btn.add_css_class("flat"); gh_btn.set_halign(Gtk.Align.CENTER)
        gh_btn.connect("clicked", lambda _: Gtk.show_uri(self, "https://github.com/calstfrancis/rubric", 0))
        box.append(gh_btn)
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_child(box); return scroll
