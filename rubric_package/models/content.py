"""Element content model — the document, with no markup language in it.

Rubric used to store element content as a Typst string and edit it through a
rich-text costume that translated back and forth. Every leak came from that:
anything the translator didn't recognise was shown to the user verbatim, so a
page of liturgy came out littered with ``#linebreak()`` nobody typed.

Content is now a list of **blocks**, each one visual line::

    {"type": "p", "runs": [{"text": "Leader:", "bold": True},
                           {"text": " This is the day."}]}

``type`` is one of :data:`BLOCK_TYPES`. ``runs`` are inline spans carrying
``bold`` / ``italic``. That is the whole format — it is what the editor edits
and what gets saved.

Typst is now an *output* format only. :func:`blocks_to_typst` renders it at
export time, and :func:`typst_to_blocks` exists to migrate services written by
older versions. Nothing in the editing path touches either.
"""

from __future__ import annotations

import re

# Block kinds. "leader" is Rubric's private leader-note block — shown in the
# manuscript, never in the bulletin.
BLOCK_TYPES = ("p", "h1", "h2", "h3", "bullet", "ordered", "leader")

Block = dict
Run = dict


# ── construction ──────────────────────────────────────────────────────────────

def make_run(text: str, bold: bool = False, italic: bool = False) -> Run:
    run: Run = {"text": text}
    if bold:
        run["bold"] = True
    if italic:
        run["italic"] = True
    return run


def make_block(btype: str = "p", runs: list[Run] | None = None) -> Block:
    return {"type": btype if btype in BLOCK_TYPES else "p", "runs": list(runs or [])}


def normalise(blocks) -> list[Block]:
    """Coerce anything loaded from disk into a valid block list.

    Files are user-editable JSON and can be hand-mangled or written by a future
    version, so this never raises — unknown block types degrade to paragraphs
    and unknown run keys are dropped.
    """
    if not isinstance(blocks, list):
        return []
    out: list[Block] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        btype = b.get("type", "p")
        if btype not in BLOCK_TYPES:
            btype = "p"
        runs: list[Run] = []
        for r in b.get("runs", []) or []:
            if not isinstance(r, dict):
                continue
            text = r.get("text", "")
            if not isinstance(text, str):
                continue
            runs.append(make_run(text, bool(r.get("bold")), bool(r.get("italic"))))
        # A block with no text has no kind worth keeping: a blank line is a
        # blank line whether it was typed inside a leader note or a heading.
        # Normalising here keeps the model and the editor in agreement — a
        # GtkTextBuffer cannot hold a tag over a zero-length range, so an empty
        # styled block would otherwise come back from the editor as a plain one
        # and register as an edit the user never made.
        if not any(r["text"].strip() for r in runs):
            btype = "p"
        out.append({"type": btype, "runs": runs})
    return out


def is_empty(blocks) -> bool:
    return not any(r.get("text", "").strip()
                   for b in normalise(blocks) for r in b["runs"])


# ── plain text ────────────────────────────────────────────────────────────────

def blocks_to_plain(blocks, include_leader: bool = True) -> str:
    """Readable text with no markup — word counts, previews, plain export."""
    lines: list[str] = []
    for b in normalise(blocks):
        if b["type"] == "leader" and not include_leader:
            continue
        lines.append("".join(r["text"] for r in b["runs"]))
    return "\n".join(lines)


def plain_to_blocks(text: str) -> list[Block]:
    """Every line becomes a paragraph. Used for pasted or generated text."""
    if not text:
        return []
    return [make_block("p", [make_run(line)] if line else [])
            for line in text.replace("\r\n", "\n").split("\n")]


def concat(a, b) -> list[Block]:
    """Join two documents with a blank line between them."""
    a, b = normalise(a), normalise(b)
    if not a:
        return b
    if not b:
        return a
    return a + [make_block("p", [])] + b


# ── Typst output ──────────────────────────────────────────────────────────────

_TYPST_SPECIAL = re.compile(r'([#$\\])')


def _escape(text: str) -> str:
    """Escape the characters Typst treats as markup.

    The editor's text is literal: if someone types ``#linebreak()`` it is those
    characters, not a function call, and must survive to the page as typed.
    """
    return _TYPST_SPECIAL.sub(r'\\\1', text)


def _runs_to_typst(runs) -> str:
    out = []
    for r in runs:
        text = _escape(r["text"])
        if not text:
            continue
        if r.get("bold") or r.get("italic"):
            # Typst won't emphasise a span that opens or closes on whitespace,
            # so the padding goes outside the markers: " go" in italics has to
            # be written " _go_", not "_ go_".
            lead = text[:len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            core = text.strip()
            if core:
                if r.get("bold"):
                    core = f"*{core}*"
                if r.get("italic"):
                    core = f"_{core}_"
            text = f"{lead}{core}{trail}"
        out.append(text)
    return "".join(out)


def blocks_to_typst(blocks) -> str:
    """Render blocks as Typst markup, for export and preview only.

    Output matches what Rubric wrote before the model change — headings as
    ``=``/``==``/``===``, lists as ``-``/``+``, hard breaks as a trailing
    ``\\``, leader blocks wrapped in ``#leader-note[…]`` — so templates and
    exporters keep working unchanged.
    """
    blocks = normalise(blocks)
    out: list[str] = []
    pending_leader: list[str] = []

    def _flush_leader() -> None:
        if not pending_leader:
            return
        # A trailing " \" before the closing bracket would escape it
        if pending_leader[-1].endswith(" \\"):
            pending_leader[-1] = pending_leader[-1][:-2]
        out.append("#leader-note[" + "\n".join(pending_leader) + "]")
        pending_leader.clear()

    for b in blocks:
        inline = _runs_to_typst(b["runs"])
        btype = b["type"]
        if btype == "leader":
            pending_leader.append(inline + (" \\" if inline.strip() else ""))
            continue
        _flush_leader()
        if btype == "h1":
            out.append(f"= {inline}")
        elif btype == "h2":
            out.append(f"== {inline}")
        elif btype == "h3":
            out.append(f"=== {inline}")
        elif btype == "bullet":
            out.append(f"- {inline}")
        elif btype == "ordered":
            out.append(f"+ {inline}")
        else:
            out.append(inline + (" \\" if inline.strip() else ""))
    _flush_leader()
    return "\n".join(out)


# ── HTML output ───────────────────────────────────────────────────────────────

def _esc_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _runs_to_html(runs) -> str:
    out = []
    for r in runs:
        text = _esc_html(r["text"])
        if not text:
            continue
        if r.get("bold"):
            text = f"<strong>{text}</strong>"
        if r.get("italic"):
            text = f"<em>{text}</em>"
        out.append(text)
    return "".join(out)


def blocks_to_html(blocks, include_leader: bool = False) -> str:
    """Render blocks as an HTML fragment for the bulletin/manuscript preview."""
    out: list[str] = []
    list_open: str | None = None

    def _close_list() -> None:
        nonlocal list_open
        if list_open:
            out.append(f"</{list_open}>")
            list_open = None

    for b in normalise(blocks):
        btype, inline = b["type"], _runs_to_html(b["runs"])
        if btype == "leader":
            _close_list()
            if include_leader:
                out.append(f'<p class="leader">{inline}</p>')
            continue
        if btype in ("bullet", "ordered"):
            want = "ul" if btype == "bullet" else "ol"
            if list_open != want:
                _close_list()
                out.append(f"<{want}>")
                list_open = want
            out.append(f"<li>{inline}</li>")
            continue
        _close_list()
        if btype in ("h1", "h2", "h3"):
            out.append(f"<{btype}>{inline}</{btype}>")
        elif inline.strip():
            out.append(f"<p>{inline}</p>")
    _close_list()
    return "\n".join(out)


# ── migration from Typst ──────────────────────────────────────────────────────

_LEADER_RE = re.compile(r'#leader-note\[(.*?)\]', re.DOTALL)
_STRONG_RE = re.compile(r'#strong\[(.*?)\]', re.DOTALL)
_EMPH_RE = re.compile(r'#emph\[(.*?)\]', re.DOTALL)
_INLINE_RE = re.compile(r'\*(.+?)\*|_(.+?)_')


_UNESCAPE_RE = re.compile(r'\\([#$\\])')


def _inline_to_runs(text: str) -> list[Run]:
    """Split a line into bold/italic runs.

    Escapes written by :func:`blocks_to_typst` are undone, so that text →
    Typst → text is stable: a literal ``#lorem(100)`` the user typed comes back
    as itself rather than accumulating backslashes.
    """
    text = _STRONG_RE.sub(lambda m: f"*{m.group(1)}*", text)
    text = _EMPH_RE.sub(lambda m: f"_{m.group(1)}_", text)

    runs: list[Run] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            runs.append(make_run(text[pos:m.start()]))
        if m.group(1) is not None:
            runs.append(make_run(m.group(1), bold=True))
        else:
            runs.append(make_run(m.group(2), italic=True))
        pos = m.end()
    if pos < len(text):
        runs.append(make_run(text[pos:]))
    for r in runs:
        r["text"] = _UNESCAPE_RE.sub(r'\1', r["text"])
    return [r for r in runs if r["text"]]


def _line_to_block(line: str, btype_default: str = "p") -> Block:
    # Layout-only calls carry no text; templates own page layout now.
    line = re.sub(r'#h\([^)]*\)', '\t', line)
    line = re.sub(r'#(colbreak|pagebreak)\(\)\s*', '', line)
    line = re.sub(r'#v\([^)]*\)\s*', '', line)
    if line.endswith(" \\"):
        line = line[:-2]

    btype = btype_default
    if line.startswith("=== "):
        btype, line = "h3", line[4:]
    elif line.startswith("== "):
        btype, line = "h2", line[3:]
    elif line.startswith("= "):
        btype, line = "h1", line[2:]
    elif line.startswith("- "):
        btype, line = "bullet", line[2:]
    elif line.startswith("+ ") or re.match(r'^\d+[.)]\s', line):
        btype = "ordered"
        line = re.sub(r'^[+\d]+[.)]?\s*', '', line)
    return make_block(btype, _inline_to_runs(line))


def typst_to_blocks(typst_str: str) -> list[Block]:
    """Parse a Typst content string into blocks — one-time migration on load.

    Only Rubric's own output subset is understood, which is all that services
    written by earlier versions contain. Anything else survives as literal text
    rather than being dropped, so no wording is ever lost in migration.
    """
    if not typst_str or not typst_str.strip():
        return []

    # A hard break is a real line break in the document model
    typst_str = re.sub(r'[ \t]*#linebreak\(\)[ \t]*\n?', '\n', typst_str)

    blocks: list[Block] = []
    pos = 0

    def _emit(segment: str, *, drop_leading_nl: bool, drop_trailing_nl: bool,
              btype: str = "p") -> None:
        # A leader-note block sits on its own line, so exactly one newline
        # separates it from its neighbours. That separator is not an empty
        # paragraph — counting it as one made blank lines multiply on every
        # save/load cycle.
        if drop_leading_nl and segment.startswith("\n"):
            segment = segment[1:]
        if drop_trailing_nl and segment.endswith("\n"):
            segment = segment[:-1]
        if not segment and (drop_leading_nl or drop_trailing_nl):
            return
        for line in segment.split("\n"):
            block = _line_to_block(line)
            block["type"] = btype if btype == "leader" else block["type"]
            blocks.append(block)

    for m in _LEADER_RE.finditer(typst_str):
        if m.start() > pos:
            # pos > 0 means this segment follows a leader block, so it carries a
            # leading separator newline as well as the trailing one.
            _emit(typst_str[pos:m.start()],
                  drop_leading_nl=pos > 0, drop_trailing_nl=True)
        _emit(m.group(1), drop_leading_nl=False, drop_trailing_nl=False, btype="leader")
        pos = m.end()
    if pos < len(typst_str):
        _emit(typst_str[pos:], drop_leading_nl=True, drop_trailing_nl=False)

    # Trim the blank lines that fall out either side of a leader-note block
    while blocks and not blocks[0]["runs"]:
        blocks.pop(0)
    while blocks and not blocks[-1]["runs"]:
        blocks.pop()
    return blocks
