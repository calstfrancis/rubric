"""BibleViewer — modal window to fetch and insert a scripture passage."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from rubric_package.utils.typst import passage_to_typst

try:
    from bible_api import fetch_passage
    _BIBLE_OK = True
except ImportError:
    _BIBLE_OK = False


class BibleViewer(Adw.Window):
    def __init__(self, reference, on_insert_cb, translation="web", esv_key="", **kw):
        super().__init__(**kw)
        self._translation = translation
        from bible_api import TRANSLATION_LABELS
        trl_label = TRANSLATION_LABELS.get(translation, translation.upper())
        self.set_title(f"{reference}  ·  {translation.upper()}"); self.set_default_size(520,460); self.set_modal(True)
        self._on_insert_cb = on_insert_cb; self._text = ""; self._ref = reference
        self._verses: list[dict] = []   # raw verse dicts from API
        tv = Adw.ToolbarView(); tv.add_top_bar(Adw.HeaderBar()); self.set_content(tv)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._status = Adw.StatusPage(title="Loading…", icon_name="content-loading-symbolic")
        self._status.set_vexpand(True); outer.append(self._status)
        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroll.set_vexpand(True); self._scroll.set_visible(False)
        self._scroll.set_margin_start(16); self._scroll.set_margin_end(16)
        self._scroll.set_margin_top(12); self._scroll.set_margin_bottom(6)
        self._tv = Gtk.TextView()
        self._tv.set_editable(False); self._tv.set_cursor_visible(False)
        self._tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR); self._tv.add_css_class("card")
        self._tv.set_top_margin(10); self._tv.set_bottom_margin(10)
        self._tv.set_left_margin(12); self._tv.set_right_margin(12)
        self._scroll.set_child(self._tv); outer.append(self._scroll)
        self._bot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._bot.set_margin_start(16); self._bot.set_margin_end(16)
        self._bot.set_margin_top(4); self._bot.set_margin_bottom(14); self._bot.set_visible(False)
        attr = Gtk.Label(label=trl_label)
        attr.add_css_class("caption"); attr.add_css_class("dim-label")
        attr.set_hexpand(True); attr.set_xalign(0); self._bot.append(attr)
        ins = Gtk.Button(label="Insert"); ins.add_css_class("suggested-action")
        ins.connect("clicked", self._on_insert); self._bot.append(ins); outer.append(self._bot)
        tv.set_content(outer)
        if _BIBLE_OK: fetch_passage(reference, self._on_fetched, translation=translation, esv_key=esv_key)
        else: self._status.set_title("Unavailable"); self._status.set_description("bible_api.py not found")

    def _on_fetched(self, text, error):
        if error:
            self._status.set_title("Could not load passage"); self._status.set_description(error)
            self._status.set_icon_name("network-error-symbolic")
        else:
            self._text = text; self._tv.get_buffer().set_text(text, -1)
            self._status.set_visible(False); self._scroll.set_visible(True); self._bot.set_visible(True)

    def _on_insert(self, _):
        if self._on_insert_cb and self._text:
            typst = passage_to_typst(self._ref, self._text, self._translation)
            self._on_insert_cb(typst)
        self.close()
