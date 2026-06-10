"""Typst ↔ GtkTextBuffer rich text converter for Rubric.

Supported round-trip subset:
  *text*            bold
  _text_            italic
  #strong[text]     bold (normalised to *text* on round-trip)
  #emph[text]       italic (normalised to _text_ on round-trip)
  = Heading         H1
  == Heading        H2
  === Heading       H3
  - item            bullet list
  + item            ordered list
  blank line        paragraph break
  #leader-note[…]  leader note block (grey in manuscript, omitted in bulletin)

Constructs outside this subset pass through as literal text in rich mode so no
data is lost when toggling to Typst source mode.
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

def typst_to_tags(typst_str: str, buf) -> bool:
    """Parse Typst markup subset and apply as tags to a GtkTextBuffer.

    Clears the buffer first.  Returns True if the source contains constructs
    outside the supported subset (caller can show a notice to the user).
    """
    ensure_tags(buf)
    buf.set_text("", 0)

    if not typst_str:
        return False

    # Convert scripture blocks to readable plain text before further parsing
    typst_str = _normalise_scripture(typst_str)

    has_unsupported = False

    # Split on #leader-note[…] blocks so leader content is tagged separately
    parts: list[tuple[bool, str]] = []
    last = 0
    for m in _LEADER_RE.finditer(typst_str):
        if m.start() > last:
            parts.append((False, typst_str[last:m.start()]))
        parts.append((True, m.group(1)))
        last = m.end()
    if last < len(typst_str):
        parts.append((False, typst_str[last:]))

    parts = [(ldr, c) for ldr, c in parts if c.strip()]

    need_nl = False
    for is_leader, content in parts:
        if need_nl:
            buf.insert(buf.get_end_iter(), '\n')
        need_nl = True

        content = content.strip('\n')
        if not content:
            need_nl = False
            continue

        if is_leader:
            ldr_start = buf.get_end_iter().get_offset()
            _insert_lines(buf, content, extra=frozenset({TAG_LEADER}))
            _apply(buf, TAG_LEADER, ldr_start, buf.get_end_iter().get_offset())
        else:
            if _insert_lines(buf, content):
                has_unsupported = True

    # Flag remaining unrecognised #func calls
    check = _LEADER_RE.sub('', typst_str)
    check = _STRONG_RE.sub('', check)
    check = _EMPH_RE.sub('', check)
    if re.search(r'#[a-zA-Z]', check):
        has_unsupported = True

    return has_unsupported


def _insert_lines(buf, text: str, extra: frozenset[str] = frozenset()) -> bool:
    """Insert multi-line text with block and inline markup tags.

    Returns True if unrecognised Typst constructs were encountered.
    """
    has_unsupported = False
    lines = text.split('\n')
    first = True

    for line in lines:
        if not first:
            buf.insert(buf.get_end_iter(), '\n')
        first = False

        # Strip Typst hard line-break suffix (appended by tags_to_typst)
        if line.endswith(' \\'):
            line = line[:-2]

        block_tag: str | None = None
        inline_text = line
        # Convert Typst tab spacing back to actual tab characters
        inline_text = re.sub(r'#h\([^)]+\)', '\t', inline_text)

        if inline_text.startswith('=== '):
            block_tag, inline_text = TAG_H3, inline_text[4:]
        elif inline_text.startswith('== '):
            block_tag, inline_text = TAG_H2, inline_text[3:]
        elif inline_text.startswith('= '):
            block_tag, inline_text = TAG_H1, inline_text[2:]
        elif inline_text.startswith('- '):
            block_tag = TAG_BULLET
            inline_text = '• ' + inline_text[2:]   # bullet character for display
        elif inline_text.startswith('+ ') or re.match(r'^\d+\.\s', inline_text):
            block_tag = TAG_ORDERED
            inline_text = re.sub(r'^[+\d]+[.) ]\s*', '', inline_text)
        elif re.search(r'#[a-zA-Z]', inline_text):
            has_unsupported = True

        tags = extra | ({block_tag} if block_tag else set())
        line_start = buf.get_end_iter().get_offset()

        for fragment, inline_tags in process_inline(inline_text):
            _insert_tagged(buf, fragment, frozenset(tags) | inline_tags)

        if block_tag:
            _apply(buf, block_tag, line_start, buf.get_end_iter().get_offset())

    return has_unsupported


# ── tags_to_typst ──────────────────────────────────────────────────────────────

def tags_to_typst(buf) -> str:
    """Convert a GtkTextBuffer with formatting tags back to Typst markup."""
    start_it = buf.get_start_iter()
    end_it   = buf.get_end_iter()

    if start_it.equal(end_it):
        return ""

    full_text = buf.get_text(start_it, end_it, False)
    if not full_text:
        return ""

    tag_table = buf.get_tag_table()
    lines     = full_text.split('\n')
    out: list[str] = []
    pending_leader: list[str] = []
    line_off = 0

    for line in lines:
        line_end = line_off + len(line)
        it = buf.get_iter_at_offset(line_off)

        def _has(tname: str) -> bool:
            tag = tag_table.lookup(tname)
            return tag is not None and it.has_tag(tag)

        is_leader = _has(TAG_LEADER)
        inline = _inline_to_typst(buf, full_text, line_off, line_end, tag_table)

        if is_leader:
            pending_leader.append(inline + (' \\' if inline.strip() else ''))
        else:
            if pending_leader:
                out.append(f'#leader-note[{chr(10).join(pending_leader)}]')
                pending_leader = []

            if _has(TAG_H3):
                out.append(f'=== {inline}')
            elif _has(TAG_H2):
                out.append(f'== {inline}')
            elif _has(TAG_H1):
                out.append(f'= {inline}')
            elif _has(TAG_BULLET):
                body = inline[2:] if inline.startswith('• ') else inline
                out.append(f'- {body}')
            elif _has(TAG_ORDERED):
                out.append(f'+ {inline}')
            else:
                out.append(inline + (' \\' if inline.strip() else ''))

        line_off = line_end + 1

    if pending_leader:
        out.append(f'#leader-note[{chr(10).join(pending_leader)}]')

    return '\n'.join(out)


def _inline_to_typst(buf, full_text: str, line_off: int, line_end: int,
                      tag_table) -> str:
    """Return Typst inline markup for the line range [line_off, line_end)."""
    if line_off >= line_end:
        return ""

    bold_tag   = tag_table.lookup(TAG_BOLD)
    italic_tag = tag_table.lookup(TAG_ITALIC)

    toggle_offs: set[int] = {line_off, line_end}
    for tag in (t for t in (bold_tag, italic_tag) if t is not None):
        it = buf.get_iter_at_offset(line_off)
        while True:
            if not it.forward_to_tag_toggle(tag):
                break
            off = it.get_offset()
            if off > line_end:
                break
            toggle_offs.add(off)

    result: list[str] = []
    for i, s in enumerate(sorted(toggle_offs)[:-1]):
        e = min(sorted(toggle_offs)[i + 1], line_end)
        if s >= line_end:
            break
        seg = full_text[s:e]
        if not seg:
            continue
        it = buf.get_iter_at_offset(s)
        bold   = bold_tag   is not None and it.has_tag(bold_tag)
        italic = italic_tag is not None and it.has_tag(italic_tag)
        seg_t = seg.replace('\t', '#h(1.5em)')
        if bold and italic:
            result.append(f'*_{seg_t}_*')
        elif bold:
            result.append(f'*{seg_t}*')
        elif italic:
            result.append(f'_{seg_t}_')
        else:
            result.append(seg_t)

    return ''.join(result)
