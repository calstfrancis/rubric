"""ElementContentWidget — rich-text content editor for Rubric service items.

Stores content as Typst internally. The user sees only a rich text editor;
raw Typst is never exposed in the UI.

An optional Rubric section (toggled via the header button) provides a private
area for leader instructions — rendered red/italic in the manuscript, stripped
from the bulletin entirely.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from rubric_package.utils.rich_typst import (
    TAG_BOLD, TAG_ITALIC, TAG_H1, TAG_H2, TAG_H3,
    TAG_LEADER, TAG_BULLET, TAG_ORDERED,
    ensure_tags, typst_to_tags, tags_to_typst,
)


class ElementContentWidget(Gtk.Box):
    """Rich-text content editor widget.

    Public API::

        set_content(typst_str)        — load Typst (suppresses change callback)
        get_content() -> str          — read current Typst string
        set_on_changed(cb)            — register cb(content: str) for user edits
        clear()                       — equivalent to set_content("")

        set_rubric_note(text)         — load rubric note text
        get_rubric_note() -> str      — read rubric note plain text
        set_on_rubric_changed(cb)     — register cb(text: str) for rubric edits
    """

    __gtype_name__ = "ElementContentWidget"

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._updating: bool = False
        self._on_changed = None
        self._on_rubric_changed = None
        self._rubric_active: bool = False
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Header row: Rubric toggle + formatting toolbar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        header.set_margin_start(4); header.set_margin_end(4)
        header.set_margin_top(4);   header.set_margin_bottom(4)

        # Rubric toggle (left side)
        self._rubric_btn = Gtk.ToggleButton(label="Rubric")
        self._rubric_btn.add_css_class("flat")
        self._rubric_btn.set_tooltip_text(
            "Show/hide the Rubric section — a private area for leader instructions.\n"
            "Rubric text appears red and italic in the manuscript only; never in the bulletin."
        )
        self._rubric_btn.connect("toggled", self._on_rubric_toggled)
        header.append(self._rubric_btn)

        sep_r = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_r.set_margin_start(4); sep_r.set_margin_end(4)
        header.append(sep_r)

        # Formatting toolbar
        self._toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._toolbar.set_hexpand(True)

        def _btn(label: str, tip: str, cb) -> Gtk.Button:
            b = Gtk.Button(label=label)
            b.add_css_class("flat")
            b.set_tooltip_text(tip)
            b.connect("clicked", cb)
            return b

        bold_btn = _btn("B",  "Bold (Ctrl+B)",   lambda _: self._apply_inline(TAG_BOLD))
        ital_btn = _btn("I",  "Italic (Ctrl+I)", lambda _: self._apply_inline(TAG_ITALIC))
        h1_btn   = _btn("H1", "Heading 1",       lambda _: self._apply_block(TAG_H1))
        h2_btn   = _btn("H2", "Heading 2",       lambda _: self._apply_block(TAG_H2))
        h3_btn   = _btn("H3", "Heading 3",       lambda _: self._apply_block(TAG_H3))
        blt_btn  = _btn("•",  "Bullet list",     lambda _: self._apply_block(TAG_BULLET))
        ord_btn  = _btn("1.", "Numbered list",   lambda _: self._apply_block(TAG_ORDERED))
        ldr_btn  = _btn("Ldr", "Leader note (private — grey block in manuscript, omitted in bulletin)",
                        lambda _: self._apply_leader())

        sep = lambda: Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)  # noqa: E731
        for w in (bold_btn, ital_btn, sep(),
                  h1_btn, h2_btn, h3_btn, sep(),
                  blt_btn, ord_btn, sep(),
                  ldr_btn):
            self._toolbar.append(w)

        header.append(self._toolbar)
        self.append(header)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Rubric note area (hidden by default) ──────────────────────────────
        self._rubric_rev = Gtk.Revealer()
        self._rubric_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._rubric_rev.set_transition_duration(150)
        self._rubric_rev.set_reveal_child(False)

        rubric_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        rubric_lbl = Gtk.Label(label="Leader instructions (manuscript only, never bulletin)")
        rubric_lbl.add_css_class("caption"); rubric_lbl.add_css_class("dim-label")
        rubric_lbl.set_xalign(0)
        rubric_lbl.set_margin_start(12); rubric_lbl.set_margin_top(6); rubric_lbl.set_margin_bottom(2)
        rubric_outer.append(rubric_lbl)

        rubric_sw = Gtk.ScrolledWindow()
        rubric_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rubric_sw.set_size_request(-1, 72)
        rubric_sw.set_margin_start(12); rubric_sw.set_margin_end(12)
        rubric_sw.set_margin_bottom(6)
        self._rubric_view = Gtk.TextView()
        self._rubric_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._rubric_view.add_css_class("rubric-note-editor")
        self._rubric_view.set_top_margin(6); self._rubric_view.set_bottom_margin(6)
        self._rubric_view.set_left_margin(8); self._rubric_view.set_right_margin(8)
        self._rubric_buf = self._rubric_view.get_buffer()
        self._rubric_buf.connect("changed", self._on_rubric_buf_changed)
        rubric_sw.set_child(self._rubric_view)
        rubric_outer.append(rubric_sw)
        rubric_outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._rubric_rev.set_child(rubric_outer)
        self.append(self._rubric_rev)

        # Notice banner: shown when typst→rich conversion loses some markup
        self._notice_rev = Gtk.Revealer()
        self._notice_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._notice_rev.set_transition_duration(150)
        notice_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        notice_box.set_margin_start(8); notice_box.set_margin_end(8)
        notice_box.set_margin_top(4);   notice_box.set_margin_bottom(4)
        notice_lbl = Gtk.Label(
            label="Some markup can't be displayed in rich text mode — shown as literal text")
        notice_lbl.add_css_class("caption")
        notice_lbl.set_hexpand(True); notice_lbl.set_xalign(0)
        dismiss_btn = Gtk.Button(icon_name="window-close-symbolic")
        dismiss_btn.add_css_class("flat")
        dismiss_btn.connect("clicked", lambda _: self._notice_rev.set_reveal_child(False))
        notice_box.append(notice_lbl)
        notice_box.append(dismiss_btn)
        self._notice_rev.set_child(notice_box)
        self.append(self._notice_rev)

        # ── Rich text editor ──────────────────────────────────────────────────
        rich_sw = Gtk.ScrolledWindow()
        rich_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rich_sw.set_vexpand(True)
        rich_sw.set_margin_start(12); rich_sw.set_margin_end(12)
        rich_sw.set_margin_top(8);    rich_sw.set_margin_bottom(8)
        self._rich_view = Gtk.TextView()
        self._rich_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._rich_view.add_css_class("card")
        self._rich_view.set_top_margin(8);   self._rich_view.set_bottom_margin(8)
        self._rich_view.set_left_margin(10); self._rich_view.set_right_margin(10)
        self._rich_buf = self._rich_view.get_buffer()
        ensure_tags(self._rich_buf)
        self._rich_buf.connect("changed", self._on_rich_changed)
        rich_sw.set_child(self._rich_view)
        self.append(rich_sw)

        # Keyboard shortcuts
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self._rich_view.add_controller(key_ctrl)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_on_changed(self, callback) -> None:
        self._on_changed = callback

    def set_on_rubric_changed(self, callback) -> None:
        self._on_rubric_changed = callback

    def set_content(self, typst_str: str) -> None:
        self._updating = True
        try:
            has_unsup = typst_to_tags(typst_str or "", self._rich_buf)
            self._notice_rev.set_reveal_child(has_unsup)
        finally:
            self._updating = False

    def get_content(self) -> str:
        return tags_to_typst(self._rich_buf)

    def clear(self) -> None:
        self.set_content("")

    def set_rubric_note(self, text: str) -> None:
        self._updating = True
        try:
            self._rubric_buf.set_text(text or "", -1)
        finally:
            self._updating = False

    def get_rubric_note(self) -> str:
        s, e = self._rubric_buf.get_bounds()
        return self._rubric_buf.get_text(s, e, False)

    # ── Rubric toggle ──────────────────────────────────────────────────────────

    def _on_rubric_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._rubric_active = btn.get_active()
        self._rubric_rev.set_reveal_child(self._rubric_active)

    # ── Formatting actions ─────────────────────────────────────────────────────

    def _apply_inline(self, tag_name: str) -> None:
        buf = self._rich_buf
        if not buf.get_has_selection():
            return
        start, end = buf.get_selection_bounds()
        tag = buf.get_tag_table().lookup(tag_name)
        if tag is None:
            return
        it = start.copy()
        all_tagged = True
        while it.compare(end) < 0:
            if not it.has_tag(tag):
                all_tagged = False
                break
            it.forward_char()
        if all_tagged:
            buf.remove_tag(tag, start, end)
        else:
            buf.apply_tag(tag, start, end)
        self._emit_changed()

    def _apply_block(self, tag_name: str) -> None:
        buf = self._rich_buf
        it = buf.get_iter_at_mark(buf.get_insert())
        line_start = it.copy(); line_start.set_line_offset(0)
        line_end = it.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        tag = buf.get_tag_table().lookup(tag_name)
        if tag is None:
            return
        if line_start.has_tag(tag):
            buf.remove_tag(tag, line_start, line_end)
        else:
            for tn in (TAG_H1, TAG_H2, TAG_H3, TAG_BULLET, TAG_ORDERED):
                t = buf.get_tag_table().lookup(tn)
                if t:
                    buf.remove_tag(t, line_start, line_end)
            buf.apply_tag(tag, line_start, line_end)
        self._emit_changed()

    def _apply_leader(self) -> None:
        buf = self._rich_buf
        it = buf.get_iter_at_mark(buf.get_insert())
        line_start = it.copy(); line_start.set_line_offset(0)
        line_end = it.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        tag = buf.get_tag_table().lookup(TAG_LEADER)
        if tag is None:
            return
        if line_start.has_tag(tag):
            buf.remove_tag(tag, line_start, line_end)
        else:
            buf.apply_tag(tag, line_start, line_end)
        self._emit_changed()

    # ── Change notifications ───────────────────────────────────────────────────

    def _on_rich_changed(self, _buf) -> None:
        if not self._updating:
            self._emit_changed()

    def _on_rubric_buf_changed(self, _buf) -> None:
        if not self._updating and self._on_rubric_changed:
            self._on_rubric_changed(self.get_rubric_note())

    def _emit_changed(self) -> None:
        if self._on_changed:
            self._on_changed(self.get_content())

    # ── Keyboard shortcuts ─────────────────────────────────────────────────────

    def _on_key_pressed(self, _ctrl, keyval, _code, state):
        CTRL = Gdk.ModifierType.CONTROL_MASK
        if state & CTRL:
            if keyval == Gdk.KEY_b:
                self._apply_inline(TAG_BOLD)
                return True
            if keyval == Gdk.KEY_i:
                self._apply_inline(TAG_ITALIC)
                return True
        return False
