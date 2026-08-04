"""Rich-text helpers for Rubric's element editor.

Converts between a document (a list of blocks — see models/content.py) and the
GtkTextBuffer the editor displays it in. Neither direction goes near a markup
language: the editor renders blocks and reads blocks back, so nothing the user
did not type can appear in their text.

Typst lives in models/content.py now, as an output format for export and as a
one-time parser for services written before the block model.
"""

from __future__ import annotations

import re

# ── Tag names ──────────────────────────────────────────────────────────────────

TAG_BOLD    = "bold"
TAG_ITALIC  = "italic"
TAG_H1      = "h1"
TAG_H2      = "h2"
TAG_H3      = "h3"
TAG_LEADER  = "leader-note"
TAG_BULLET  = "bullet"
TAG_ORDERED = "ordered"

# ── Compiled patterns ──────────────────────────────────────────────────────────

# One level of nested brackets — sufficient for #sverse(N)[text] inside #scripture
# and #strong[text] / #emph[text] inside #leader-note
_LEADER_RE    = re.compile(r'#leader-note\[((?:[^[\]]|\[[^\]]*\])*)\]', re.DOTALL)
_STRONG_RE    = re.compile(r'#strong\[((?:[^[\]]|\[[^\]]*\])*)\]')
_EMPH_RE      = re.compile(r'#emph\[((?:[^[\]]|\[[^\]]*\])*)\]')
_INLINE_RE    = re.compile(r'(\*[^*\n]+\*|_[^_\n]+_)')
# Scripture blocks: #text(...)[ref] + #scripture[#sverse(n)[...] ...]
_SCRIPTURE_RE = re.compile(
    r'#text\([^)]*\)\[([^\]]+)\]\s*\n#scripture\[((?:[^[\]]|\[[^\]]*\])*)\]',
    re.DOTALL,
)
_SVERSE_RE    = re.compile(r'#sverse\((\d+)\)\[([^\]]*)\]')


def _scripture_to_plain(m: re.Match) -> str:
    """Convert a #text(...)[ref] + #scripture[...] block to readable plain text."""
    ref = m.group(1).strip()
    body = m.group(2)
    verses = _SVERSE_RE.findall(body)
    lines = [f"³³{num}³³ {text.strip()}" for num, text in verses]
    # Use a simple marker: reference line then indented verse lines
    return ref + "\n" + "\n".join("    " + l for l in lines) if lines else ref


def _normalise_scripture(text: str) -> str:
    """Replace #scripture blocks with readable plain-text before tag parsing."""
    return _SCRIPTURE_RE.sub(_scripture_to_plain, text)


# ── Tag management ─────────────────────────────────────────────────────────────

def ensure_tags(buf) -> None:
    """Create standard formatting tags in the GtkTextBuffer if absent."""
    tag_table = buf.get_tag_table()

    def _mk(name: str, **kw) -> None:
        if tag_table.lookup(name) is None:
            buf.create_tag(name, **kw)

    try:
        from gi.repository import Pango
        _mk(TAG_BOLD,   weight=Pango.Weight.BOLD)
        _mk(TAG_ITALIC, style=Pango.Style.ITALIC)
        _mk(TAG_H1,     weight=Pango.Weight.BOLD, scale=1.4)
        _mk(TAG_H2,     weight=Pango.Weight.BOLD, scale=1.2)
        _mk(TAG_H3,     weight=Pango.Weight.BOLD, scale=1.05)
        _mk(TAG_LEADER,  background="#fff0f0", foreground="#b91c1c",
            style=Pango.Style.ITALIC,
            left_margin=12, right_margin=12,
            pixels_above_lines=4, pixels_below_lines=4)
    except ImportError:
        for name in (TAG_BOLD, TAG_ITALIC, TAG_H1, TAG_H2, TAG_H3):
            _mk(name)
        _mk(TAG_LEADER,  background="#fff0f0", foreground="#b91c1c",
            left_margin=12, right_margin=12,
            pixels_above_lines=4, pixels_below_lines=4)
    _mk(TAG_BULLET,  left_margin=24)
    _mk(TAG_ORDERED, left_margin=24)


# ── Inline parsing (pure Python — unit-testable without GTK) ──────────────────

def process_inline(text: str) -> list[tuple[str, frozenset[str]]]:
    """Parse *bold* / _italic_ inline markup from a Typst string fragment.

    Returns a list of ``(fragment, tags)`` pairs.  Tags is a frozenset of
    tag-name strings.  Normalises #strong[…] and #emph[…] before parsing.
    """
    text = _STRONG_RE.sub(r'*\1*', text)
    text = _EMPH_RE.sub(r'_\1_', text)

    result: list[tuple[str, frozenset[str]]] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            result.append((text[pos:m.start()], frozenset()))
        raw = m.group(0)
        if raw[0] == '*':
            result.append((raw[1:-1], frozenset({TAG_BOLD})))
        else:
            result.append((raw[1:-1], frozenset({TAG_ITALIC})))
        pos = m.end()
    if pos < len(text):
        result.append((text[pos:], frozenset()))
    return result


# ── Buffer helpers ─────────────────────────────────────────────────────────────

def _apply(buf, tag_name: str, start_off: int, end_off: int) -> None:
    if start_off >= end_off:
        return
    s = buf.get_iter_at_offset(start_off)
    e = buf.get_iter_at_offset(end_off)
    buf.apply_tag_by_name(tag_name, s, e)


def _insert_tagged(buf, text: str, tags: frozenset[str]) -> None:
    if not text:
        return
    start_off = buf.get_end_iter().get_offset()
    buf.insert(buf.get_end_iter(), text)
    for tn in tags:
        _apply(buf, tn, start_off, buf.get_end_iter().get_offset())


# ── typst_to_tags ──────────────────────────────────────────────────────────────

_BLOCK_TAGS = {
    "h1": TAG_H1, "h2": TAG_H2, "h3": TAG_H3,
    "bullet": TAG_BULLET, "ordered": TAG_ORDERED, "leader": TAG_LEADER,
}
_TAG_BLOCKS = {v: k for k, v in _BLOCK_TAGS.items()}


def blocks_to_buffer(blocks, buf) -> None:
    """Fill a GtkTextBuffer from a block list."""
    from rubric_package.models.content import normalise

    ensure_tags(buf)
    buf.set_text("", 0)
    first = True
    for block in normalise(blocks):
        if not first:
            buf.insert(buf.get_end_iter(), "\n")
        first = False

        line_start = buf.get_end_iter().get_offset()
        btype = block["type"]
        prefix = "\u2022 " if btype == "bullet" else ""
        if prefix:
            _insert_tagged(buf, prefix, frozenset())
        for run in block["runs"]:
            tags = set()
            if run.get("bold"):
                tags.add(TAG_BOLD)
            if run.get("italic"):
                tags.add(TAG_ITALIC)
            _insert_tagged(buf, run["text"], frozenset(tags))
        block_tag = _BLOCK_TAGS.get(btype)
        if block_tag:
            _apply(buf, block_tag, line_start, buf.get_end_iter().get_offset())


def buffer_to_blocks(buf) -> list[dict]:
    """Read a GtkTextBuffer back into a block list."""
    from rubric_package.models.content import make_block, make_run

    start_it, end_it = buf.get_start_iter(), buf.get_end_iter()
    full_text = buf.get_text(start_it, end_it, False)
    if not full_text:
        return []

    table = buf.get_tag_table()
    bold_tag = table.lookup(TAG_BOLD)
    ital_tag = table.lookup(TAG_ITALIC)

    blocks: list[dict] = []
    line_off = 0
    for line in full_text.split("\n"):
        line_end = line_off + len(line)
        it = buf.get_iter_at_offset(line_off)

        btype = "p"
        for tag_name, name in _TAG_BLOCKS.items():
            tag = table.lookup(tag_name)
            if tag is not None and it.has_tag(tag):
                btype = name
                break

        text = line
        start = line_off
        if btype == "bullet" and text.startswith("\u2022 "):
            text = text[2:]
            start += 2

        runs = []
        cur, cur_bold, cur_ital = "", None, None
        for i, ch in enumerate(text):
            ci = buf.get_iter_at_offset(start + i)
            b = bold_tag is not None and ci.has_tag(bold_tag)
            v = ital_tag is not None and ci.has_tag(ital_tag)
            if (b, v) != (cur_bold, cur_ital) and cur:
                runs.append(make_run(cur, bool(cur_bold), bool(cur_ital)))
                cur = ""
            cur_bold, cur_ital = b, v
            cur += ch
        if cur:
            runs.append(make_run(cur, bool(cur_bold), bool(cur_ital)))

        blocks.append(make_block(btype, runs))
        line_off = line_end + 1
    return blocks


