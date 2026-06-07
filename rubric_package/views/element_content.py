"""ElementContentWidget — dual-mode content editor for Rubric service items.

Replaces the three-tab (Leader / Bulletin / Prep) notes stack with a single
unified editor that stores content as Typst internally.  Two editing modes:

  Rich text  (default) — GtkTextView with formatting toolbar (B / I / headings /
                          lists / leader-note).  Keyboard: Ctrl+B, Ctrl+I.
  Typst mode           — GtkSourceView (or plain GtkTextView fallback) showing
                          the raw Typst source with syntax highlighting.

A toggle button in the top-right corner switches modes; switching preserves
content via tags_to_typst / typst_to_tags.
"""

from __future__ import annotations

from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

# Optional: GtkSourceView for Typst-mode syntax highlighting
_GSOURCE_OK = False
try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource as _GtkSource  # type: ignore[attr-defined]
    _GSOURCE_OK = True
except Exception:
    _GtkSource = None  # type: ignore[assignment]

from rubric_package.utils.rich_typst import (
    TAG_BOLD, TAG_ITALIC, TAG_H1, TAG_H2, TAG_H3,
    TAG_LEADER, TAG_BULLET, TAG_ORDERED,
    ensure_tags, typst_to_tags, tags_to_typst,
)


def _init_source_language_manager() -> None:
    """Register bundled typst.lang with the GtkSourceView language manager."""
    if not _GSOURCE_OK:
        return
    data_dir = str(Path(__file__).parent.parent / "data")
    lm = _GtkSource.LanguageManager.get_default()
    existing = list(lm.get_search_path())
    if data_dir not in existing:
        lm.set_search_path([data_dir] + existing)


def _get_typst_language():
    """Return the GtkSource.Language for Typst, or None."""
    if not _GSOURCE_OK:
        return None
    _init_source_language_manager()
    lm = _GtkSource.LanguageManager.get_default()
    return lm.get_language("typst")


class ElementContentWidget(Gtk.Box):
    """Dual-mode content editor widget.

    Public API::

        set_content(typst_str)  — load Typst (suppresses change callback)
        get_content() -> str    — read current Typst string
        set_on_changed(cb)      — register cb(content: str) for user edits
        clear()                 — equivalent to set_content("")
    """

    __gtype_name__ = "ElementContentWidget"

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._mode: str = "rich"          # "rich" | "typst"
        self._updating: bool = False      # True while set_content() is running
        self._on_changed = None           # callback(content: str) | None
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Header row: formatting toolbar + mode toggle
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        header.set_margin_start(4); header.set_margin_end(4)
        header.set_margin_top(4);   header.set_margin_bottom(4)

        self._toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._toolbar.set_hexpand(True)

        def _btn(label: str, tip: str, cb) -> Gtk.Button:
            b = Gtk.Button(label=label)
            b.add_css_class("flat")
            b.set_tooltip_text(tip)
            b.connect("clicked", cb)
            return b

        bold_btn = _btn("B",  "Bold (Ctrl+B)",           lambda _: self._apply_inline(TAG_BOLD))
        ital_btn = _btn("I",  "Italic (Ctrl+I)",         lambda _: self._apply_inline(TAG_ITALIC))
        h1_btn   = _btn("H1", "Heading 1",               lambda _: self._apply_block(TAG_H1))
        h2_btn   = _btn("H2", "Heading 2",               lambda _: self._apply_block(TAG_H2))
        h3_btn   = _btn("H3", "Heading 3",               lambda _: self._apply_block(TAG_H3))
        blt_btn  = _btn("•",  "Bullet list",             lambda _: self._apply_block(TAG_BULLET))
        ord_btn  = _btn("1.", "Numbered list",           lambda _: self._apply_block(TAG_ORDERED))
        ldr_btn  = _btn("Ldr","Leader note (private, not in bulletin)",
                        lambda _: self._apply_leader())

        sep = lambda: Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)  # noqa: E731
        for w in (bold_btn, ital_btn, sep(),
                  h1_btn, h2_btn, h3_btn, sep(),
                  blt_btn, ord_btn, sep(),
                  ldr_btn):
            self._toolbar.append(w)

        spacer = Gtk.Label()
        spacer.set_hexpand(True)

        self._mode_btn = Gtk.ToggleButton(label="Typst")
        self._mode_btn.add_css_class("flat")
        self._mode_btn.set_tooltip_text("Toggle raw Typst source mode")
        self._mode_btn.connect("toggled", self._on_mode_toggled)

        header.append(self._toolbar)
        header.append(spacer)
        header.append(self._mode_btn)
        self.append(header)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Notice banner: shown when switching typst→rich and unsupported markup found
        self._notice_rev = Gtk.Revealer()
        self._notice_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._notice_rev.set_transition_duration(150)
        notice_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        notice_box.set_margin_start(8); notice_box.set_margin_end(8)
        notice_box.set_margin_top(4);   notice_box.set_margin_bottom(4)
        notice_lbl = Gtk.Label(
            label="Some Typst markup can't be shown in rich text mode — displayed as literal text")
        notice_lbl.add_css_class("caption")
        notice_lbl.set_hexpand(True); notice_lbl.set_xalign(0)
        dismiss_btn = Gtk.Button(icon_name="window-close-symbolic")
        dismiss_btn.add_css_class("flat")
        dismiss_btn.connect("clicked", lambda _: self._notice_rev.set_reveal_child(False))
        notice_box.append(notice_lbl)
        notice_box.append(dismiss_btn)
        self._notice_rev.set_child(notice_box)
        self.append(self._notice_rev)

        # Content stack: rich | typst
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)

        # Rich text view
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
        self._stack.add_named(rich_sw, "rich")

        # Raw Typst view (GtkSourceView if available, plain TextView otherwise)
        typst_sw = Gtk.ScrolledWindow()
        typst_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        typst_sw.set_vexpand(True)
        typst_sw.set_margin_start(12); typst_sw.set_margin_end(12)
        typst_sw.set_margin_top(8);    typst_sw.set_margin_bottom(8)

        if _GSOURCE_OK:
            lang = _get_typst_language()
            self._typst_src_buf = _GtkSource.Buffer()
            if lang:
                self._typst_src_buf.set_language(lang)
            sm = _GtkSource.StyleSchemeManager.get_default()
            scheme = sm.get_scheme("classic") or sm.get_scheme("tango")
            if scheme:
                self._typst_src_buf.set_style_scheme(scheme)
            self._typst_src_buf.set_highlight_syntax(True)
            self._typst_view = _GtkSource.View.new_with_buffer(self._typst_src_buf)
            self._typst_buf = self._typst_src_buf
            # Error line highlighting tag
            self._err_tag = self._typst_src_buf.create_tag(
                "error-line", background="#ffcccc", paragraph_background="#ffcccc"
            )
        else:
            self._typst_view = Gtk.TextView()
            self._typst_buf = self._typst_view.get_buffer()
            self._err_tag = None

        self._typst_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._typst_view.add_css_class("card")
        self._typst_view.add_css_class("monospace")
        self._typst_view.set_top_margin(8);   self._typst_view.set_bottom_margin(8)
        self._typst_view.set_left_margin(10); self._typst_view.set_right_margin(10)
        self._typst_buf.connect("changed", self._on_typst_changed)
        typst_sw.set_child(self._typst_view)
        self._stack.add_named(typst_sw, "typst")

        self.append(self._stack)

        # Keyboard shortcuts (rich mode only)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self._rich_view.add_controller(key_ctrl)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_on_changed(self, callback) -> None:
        """Register callback(content: str) invoked on every user edit."""
        self._on_changed = callback

    def set_content(self, typst_str: str) -> None:
        """Load Typst content without triggering the change callback."""
        self._updating = True
        try:
            if self._mode == "rich":
                has_unsup = typst_to_tags(typst_str or "", self._rich_buf)
                self._notice_rev.set_reveal_child(has_unsup)
            else:
                self._typst_buf.set_text(typst_str or "", -1)
        finally:
            self._updating = False

    def get_content(self) -> str:
        """Return the current content as a Typst string."""
        if self._mode == "rich":
            return tags_to_typst(self._rich_buf)
        s, e = self._typst_buf.get_bounds()
        return self._typst_buf.get_text(s, e, False)

    def clear(self) -> None:
        self.set_content("")

    # ── Mode toggle ────────────────────────────────────────────────────────────

    def _on_mode_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            # rich → typst
            typst = tags_to_typst(self._rich_buf)
            self._mode = "typst"
            self._stack.set_visible_child_name("typst")
            self._toolbar.set_visible(False)
            self._notice_rev.set_reveal_child(False)
            self._updating = True
            self._typst_buf.set_text(typst or "", -1)
            self._updating = False
        else:
            # typst → rich
            s, e = self._typst_buf.get_bounds()
            typst = self._typst_buf.get_text(s, e, False)
            self._mode = "rich"
            self._stack.set_visible_child_name("rich")
            self._toolbar.set_visible(True)
            self._updating = True
            has_unsup = typst_to_tags(typst, self._rich_buf)
            self._updating = False
            self._notice_rev.set_reveal_child(has_unsup)

    # ── Formatting actions ─────────────────────────────────────────────────────

    def _apply_inline(self, tag_name: str) -> None:
        """Toggle inline formatting (bold/italic) on current selection."""
        buf = self._rich_buf
        if not buf.get_has_selection():
            return
        start, end = buf.get_selection_bounds()
        tag = buf.get_tag_table().lookup(tag_name)
        if tag is None:
            return
        # If every character in selection already has the tag, remove; else apply
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
        """Apply/remove block tag (heading, list) on the current line."""
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
        """Toggle the leader-note block tag on the current line."""
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

    def _on_typst_changed(self, _buf) -> None:
        if not self._updating:
            self._emit_changed()

    def _emit_changed(self) -> None:
        if self._on_changed:
            self._on_changed(self.get_content())

    # ── Error highlighting ─────────────────────────────────────────────────────

    def mark_error_line(self, line: int | None) -> None:
        """Highlight a 1-based line number in Typst mode (None clears)."""
        if self._err_tag is None:
            return
        start, end = self._typst_buf.get_bounds()
        self._typst_buf.remove_tag(self._err_tag, start, end)
        if line is None or line < 1:
            return
        line_iter = self._typst_buf.get_iter_at_line(line - 1)
        if line_iter is None:
            return
        line_end = line_iter.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        self._typst_buf.apply_tag(self._err_tag, line_iter, line_end)

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
