"""ServicePlanningNotesWindow — pop-out editor window for freeform service-planning notes."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class ServicePlanningNotesWindow(Adw.Window):
    def __init__(self, buffer: Gtk.TextBuffer, **kw):
        super().__init__(title="Service Notes", default_width=520, default_height=400, **kw)
        self.set_hide_on_close(True)

        tv_view = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        tv_view.add_top_bar(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        tv = Gtk.TextView(buffer=buffer)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_accepts_tab(False)
        tv.set_left_margin(18); tv.set_right_margin(18)
        tv.set_top_margin(12); tv.set_bottom_margin(12)
        scroll.set_child(tv)
        tv_view.set_content(scroll)
        self.set_content(tv_view)
