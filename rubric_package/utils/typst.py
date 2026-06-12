"""Typst utility functions for Rubric."""

from __future__ import annotations

import re


# Characters that have special meaning in Typst markup mode.
_TYPST_ESCAPES = [
    ("\\", "\\u{5c}"),   # literal backslash — must be first
    ("#",  "\\#"),
    ("@",  "\\@"),
    ("*",  "\\*"),
    ("_",  "\\_"),
    ("~",  "\\~"),
    ("$",  "\\$"),
    ("`",  "\\`"),
    ("<",  "\\<"),
    (">",  "\\>"),
]


def typst_escape(text: str) -> str:
    """Escape special Typst markup characters in plain text."""
    for char, escaped in _TYPST_ESCAPES:
        text = text.replace(char, escaped)
    return text


def note_for_typst(note: str) -> str:
    """Prepare a note for Typst insertion.

    If the note already contains Typst function calls (lines starting with #
    followed by a letter), pass through as-is so hand-written Typst works.
    Otherwise escape special characters.
    """
    if not note:
        return ""
    if re.search(r"(?m)^#[a-zA-Z]", note):
        return note
    return typst_escape(note)


def strip_leader_notes(text: str) -> str:
    """Remove #leader-note[...] and #rubric-note[...] blocks for congregation-facing output."""
    text = re.sub(
        r'#leader-note\[((?:[^[\]]|\[[^\]]*\])*)\]', '', text, flags=re.DOTALL
    )
    text = re.sub(
        r'#rubric-note\[((?:[^[\]]|\[[^\]]*\])*)\]', '', text, flags=re.DOTALL
    )
    return text.strip()


def passage_to_typst(reference: str, text: str, translation: str = "web") -> str:
    """Convert Bible verse text to a Typst scripture block.

    Args:
        reference:   Bible reference, e.g. "John 3:16"
        text:        Verse text from the Bible API
        translation: Translation key (web, kjv, asv, esv)

    Returns:
        Typst source string for the scripture block.
    """
    lines = text.strip().splitlines()

    verses: list[tuple[str, str]] = []
    current_num: str | None = None
    current_parts: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\s*(.*)", line)
        if m:
            if current_num is not None:
                verses.append((current_num, " ".join(current_parts)))
            current_num = m.group(1)
            current_parts = [m.group(2).strip()] if m.group(2).strip() else []
        else:
            if current_num is not None:
                current_parts.append(line)

    if current_num is not None:
        verses.append((current_num, " ".join(current_parts)))

    ref_esc = typst_escape(reference)
    trl_label = translation.upper()

    verse_lines = [f"  #sverse({vnum})[{typst_escape(vtext)}]" for vnum, vtext in verses]
    verse_block = "\n".join(verse_lines)

    return (
        f"#text(size: 0.85em, style: \"italic\")[{ref_esc} ({trl_label})]\n"
        f"#scripture[\n{verse_block}\n]"
    )


def strip_typst_for_html(text: str) -> str:
    """Strip Typst (or legacy LaTeX) markup, returning HTML-safe text.

    Used by the HTML bulletin preview where markup should be rendered
    as formatted HTML, not raw Typst source.
    """
    import re as _re

    # ── Typst scripture → HTML ────────────────────────────────────────────────
    def _render_scripture(m: re.Match) -> str:
        inner = m.group(1)
        inner = _re.sub(
            r"#sverse\((\d+)\)\[([^\]]*)\]",
            r"<sup>\1</sup>&nbsp;\2",
            inner,
        )
        return inner

    text = _re.sub(r"#scripture\[((?:[^[\]]|\[[^\]]*\])*)\]", _render_scripture, text, flags=_re.DOTALL)

    # ── Typst inline formatting → HTML ────────────────────────────────────────
    text = _re.sub(r"#strong\[([^\]]*)\]", r"<strong>\1</strong>", text)
    text = _re.sub(r"#emph\[([^\]]*)\]",   r"<em>\1</em>",         text)
    text = _re.sub(r"\*([^*\n]+)\*",        r"<strong>\1</strong>", text)
    text = _re.sub(r"_([^_\n]+)_",          r"<em>\1</em>",         text)

    # Strip leader-note and rubric-note blocks entirely (congregation HTML)
    text = _re.sub(r"#leader-note\[((?:[^[\]]|\[[^\]]*\])*)\]", "", text, flags=_re.DOTALL)
    text = _re.sub(r"#rubric-note\[((?:[^[\]]|\[[^\]]*\])*)\]", "", text, flags=_re.DOTALL)

    # Strip remaining Typst function calls — emit their content arg if present
    text = _re.sub(r"#[a-z][a-z-]*\((?:[^()]*)\)", "", text)
    text = _re.sub(r"#[a-z][a-z-]*\[([^\]]*)\]",    r"\1", text)
    text = _re.sub(r"#[a-z][a-z-]*",                 "",    text)

    # ── Legacy LaTeX → HTML (backward compat for existing .liturgy files) ─────
    text = _re.sub(
        r"\\begin\{scripture\}(.*?)\\end\{scripture\}",
        lambda m: _re.sub(
            r"\\sverse\{(\d+)\}\{([^}]+)\}",
            r"<sup>\1</sup>&nbsp;\2",
            m.group(1).strip(),
        ),
        text,
        flags=_re.DOTALL,
    )
    text = _re.sub(r"\\textbf\{([^}]*)\}", r"<strong>\1</strong>", text)
    text = _re.sub(r"\\textit\{([^}]*)\}", r"<em>\1</em>",         text)
    text = _re.sub(r"\\emph\{([^}]*)\}",   r"<em>\1</em>",         text)
    text = _re.sub(r"\\\\",                 "<br>",                 text)
    text = _re.sub(r"\\(?:hspace|vspace)\*?\{[^}]*\}", "", text)
    text = _re.sub(
        r"\\(?:noindent|newline|newpage|pagebreak|clearpage|par"
        r"|medskip|bigskip|smallskip|linebreak|centering)\b\s*",
        " ", text,
    )
    text = _re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", text)
    text = _re.sub(r"\\[a-zA-Z]+\*?\s*",          "",   text)

    # ── Typst heading syntax → HTML (after all # stripping so styles survive) ─
    text = _re.sub(r"^=== (.+)$", r"<strong>\1</strong>", text, flags=_re.MULTILINE)
    text = _re.sub(
        r"^== (.+)$",
        r"<b style='display:block;font-variant:small-caps;"
        r"border-bottom:1px solid silver;margin:6px 0 2px'>\1</b>",
        text, flags=_re.MULTILINE,
    )
    text = _re.sub(
        r"^= (.+)$",
        r"<b style='display:block;font-size:1.15em;text-align:center;margin:10px 0 4px'>\1</b>",
        text, flags=_re.MULTILINE,
    )


    return text.strip()


def parse_typst_errors(stderr: str) -> list[dict]:
    """Parse typst compile stderr into a list of structured error dicts.

    Each dict has keys: message (str), file (str|None), line (int|None), col (int|None).

    Example stderr line:
        error: unclosed delimiter
          --> rubric_preview_xxx.typ:42:15
    """
    errors: list[dict] = []
    lines = stderr.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("error:"):
            msg = line[6:].strip()
            entry: dict = {"message": msg, "file": None, "line": None, "col": None}
            if i + 1 < len(lines):
                m = re.match(r"\s+-->\s+(.+):(\d+):(\d+)", lines[i + 1])
                if m:
                    entry["file"] = m.group(1)
                    entry["line"] = int(m.group(2))
                    entry["col"] = int(m.group(3))
                    i += 1
            errors.append(entry)
        i += 1
    return errors


_FRIENDLY_ERRORS = [
    (r"expected closing `\}`",
     "An opening `{` was never closed — check for a missing `}` near this line"),
    (r"expected closing `\]`",
     "A `[` was opened but never closed — check for a missing `]`"),
    (r"expected closing `\)`",
     "A `(` was opened but never closed — check for a missing `)`"),
    (r"unknown variable[^`]*`([^`]+)`",
     "'{0}' isn't recognised — remove the # or check the spelling"),
    (r"not found in scope[^`]*`([^`]+)`",
     "'{0}' couldn't be found — check the spelling or remove the #"),
    (r"bibliography.*not found|bib.*file.*not.*found|cannot open.*\.bib",
     "The bibliography file (.bib) wasn't found — check the path in Settings → Bibliography"),
    (r"file not found|cannot open|no such file",
     "A referenced file is missing — make sure all linked files are in the same folder"),
    (r"font.*not found|cannot find font",
     "A font isn't installed — try a different font in Settings, or install the missing one"),
    (r"expected content",
     "There's a formatting problem near this line — check for unclosed brackets or stray #"),
    (r"unexpected end of file",
     "The document ended unexpectedly — an opening bracket or block was never closed"),
    (r"cannot convert|type mismatch",
     "A value in your document is the wrong type — check numbers vs. text in function arguments"),
]


def format_typst_error(stderr: str) -> str:
    """Return a plain-English error string from typst stderr."""
    errors = parse_typst_errors(stderr)
    raw_msg = errors[0]["message"] if errors else (stderr.strip().splitlines() or [""])[-1]
    line_no = errors[0]["line"] if errors else None
    loc = f" (line {line_no})" if line_no else ""

    import re as _re
    for pattern, friendly in _FRIENDLY_ERRORS:
        m = _re.search(pattern, raw_msg, _re.IGNORECASE)
        if m:
            try:
                msg = friendly.format(*m.groups())
            except (IndexError, KeyError):
                msg = friendly
            return msg + loc

    return raw_msg[:140] + loc


def strip_typst_plain(text: str) -> str:
    """Strip Typst (or legacy LaTeX) markup, returning plain text.

    Used for plain-text contexts (CSV export, copy-as-text, etc.).
    """
    import re as _re

    # Typst scripture
    text = _re.sub(
        r"#scripture\[((?:[^[\]]|\[[^\]]*\])*)\]",
        lambda m: _re.sub(r"#sverse\((\d+)\)\[([^\]]*)\]", r"\1 \2 ", m.group(1).strip()),
        text, flags=_re.DOTALL,
    )
    # Leader/rubric notes — strip
    text = _re.sub(r"#leader-note\[((?:[^[\]]|\[[^\]]*\])*)\]", "", text, flags=_re.DOTALL)
    text = _re.sub(r"#rubric-note\[((?:[^[\]]|\[[^\]]*\])*)\]", "", text, flags=_re.DOTALL)
    # Typst formatting — keep content
    text = _re.sub(r"#[a-z][a-z-]*\[([^\]]*)\]", r"\1", text)
    text = _re.sub(r"#[a-z][a-z-]*\((?:[^()]*)\)", "", text)
    text = _re.sub(r"#[a-z][a-z-]*", "", text)
    text = _re.sub(r"\*([^*\n]+)\*", r"\1", text)
    text = _re.sub(r"_([^_\n]+)_",   r"\1", text)
    # Legacy LaTeX
    text = _re.sub(
        r"\\begin\{scripture\}(.*?)\\end\{scripture\}",
        lambda m: _re.sub(r"\\sverse\{(\d+)\}\{([^}]*)\}", r"\1 \2 ", m.group(1).strip()),
        text, flags=_re.DOTALL,
    )
    text = _re.sub(r"\\(?:textbf|textit|emph|small)\{([^}]*)\}", r"\1", text)
    text = _re.sub(r"\\(?:hspace|vspace)\*?\{[^}]*\}", "", text)
    text = _re.sub(r"\\\\", "\n", text)
    text = _re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", text)
    text = _re.sub(r"\\[a-zA-Z@]+\*?", "", text)
    text = _re.sub(r"[{}]", "", text)
    return text.strip()


# ── Shared Typst function definitions ─────────────────────────────────────────
# Inlined into every generated .typ document.

TYPST_SHARED = r"""
// ── Rubric shared functions ───────────────────────────────────────────────────

#let movement(title) = {
  v(8pt)
  align(center, text(weight: "bold", size: 1.2em, smallcaps(title)))
  v(4pt)
}

#let hymnref(ref, title) = {
  strong(ref)
  h(0.3em)
  emph(title)
}

#let ldr(content) = { strong(content); linebreak() }
#let ppl(content) = { strong(content); linebreak() }

#let sverse(num, content) = {
  super(str(num))
  h(0.25em)
  content
  linebreak()
}

#let scripture(content) = block(
  inset: (left: 1.5em),
  above: 4pt,
  below: 4pt,
  content,
)

#let leader-note(content) = block(
  fill: rgb("#fff0f0"),
  inset: (left: 10pt, right: 10pt, top: 6pt, bottom: 6pt),
  radius: 4pt,
  above: 4pt,
  below: 4pt,
  text(size: 0.9em, fill: rgb("#b91c1c"), style: "italic", content),
)

#let rubric-note(content) = block(
  fill: rgb("#fff0f0"),
  inset: (left: 10pt, right: 10pt, top: 6pt, bottom: 6pt),
  radius: 4pt,
  above: 4pt,
  below: 4pt,
  text(size: 0.9em, fill: rgb("#b91c1c"), style: "italic", content),
)

// Section heading: centred large bold small-caps (= Section)
#show heading.where(level: 1): it => {
  v(10pt, weak: true)
  align(center, text(size: 1.3em, weight: "bold", smallcaps(it.body)))
  v(6pt, weak: true)
}

// Element heading: bold small-caps with a thin rule below (== Item)
#show heading.where(level: 2): it => {
  v(6pt, weak: true)
  text(weight: "bold", smallcaps(it.body))
  v(1pt, weak: true)
  line(length: 100%, stroke: 0.4pt + luma(160))
  v(4pt, weak: true)
}

// Sub-heading: medium bold (=== Subitem)
#show heading.where(level: 3): it => {
  v(4pt, weak: true)
  text(size: 0.95em, weight: "bold", it.body)
  v(2pt, weak: true)
}
""".strip()
