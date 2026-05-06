"""LaTeX utility functions for Rubric."""

from __future__ import annotations

import re


def latex_escape(text: str) -> str:
    """Escape special LaTeX characters in text."""
    replacements = [
        ("\\", "\\textbackslash{}"),
        ("&", "\\&"),
        ("%", "\\%"),
        ("$", "\\$"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
    ]
    for char, escaped in replacements:
        text = text.replace(char, escaped)
    return text


def note_for_latex(note: str) -> str:
    """Prepare a note for LaTeX export.

    If the note contains LaTeX commands (lines starting with \),
    use it as-is. Otherwise, escape special characters.
    """
    if not note:
        return ""
    if any(line.strip().startswith("\\") for line in note.splitlines()):
        return note
    return latex_escape(note)


def passage_to_latex(reference: str, text: str) -> str:
    r"""
    Convert WEB verse text to LaTeX inside a {scripture} environment.

    The API sometimes splits a single verse across multiple lines;
    we join all lines until the next numbered verse into one \sverse call.

    Args:
        reference: Bible reference (e.g., "John 3:16")
        text: Verse text from WEB API

    Returns:
        LaTeX code for the scripture environment
    """
    lines = text.strip().splitlines()

    # First pass: group lines into (verse_num, full_text) pairs
    verses: list[tuple[str, str]] = []
    current_num: str | None = None
    current_parts: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\s*(.*)", line)
        if m:
            # Save previous verse if any
            if current_num is not None:
                verses.append((current_num, " ".join(current_parts)))
            current_num = m.group(1)
            current_parts = [m.group(2).strip()] if m.group(2).strip() else []
        else:
            # Continuation of the current verse
            if current_num is not None:
                current_parts.append(line)
            # else: text before any verse number -- ignore

    # Flush last verse
    if current_num is not None:
        verses.append((current_num, " ".join(current_parts)))

    latex_lines = []
    for vnum, vtext in verses:
        latex_lines.append(f"\\sverse{{{vnum}}}{{{latex_escape(vtext)}}}")

    ref_escaped = latex_escape(reference)
    body = "\n".join(latex_lines)
    return (
        f"% {ref_escaped} (WEB)\n"
        f"{{\\small\\textit{{{ref_escaped} (WEB)}}}}\n"
        f"\\begin{{scripture}}\n"
        f"{body}\n"
        f"\\end{{scripture}}"
    )


def migrate_scripture_note(note: str) -> str:
    """Migrate old scripture format to new {scripture} environment."""
    if r"\begin{quotation}" not in note:
        return note

    lines = note.splitlines()
    pre: list[str] = []
    verses: list[str] = []
    post: list[str] = []
    ref_line = ""
    in_q = False
    after_q = False

    for line in lines:
        s = line.strip()
        if s == r"\begin{quotation}":
            in_q = True
            continue
        if s == r"\end{quotation}":
            in_q = False
            after_q = True
            continue
        if after_q:
            post.append(line)
            continue
        if not in_q:
            pre.append(line)
            continue
        if not s:
            continue
        if s.startswith(r"\textit{") or s.startswith("% "):
            m = re.search(r"\\textit\{\\small ([^}]+)\}", s)
            ref_line = "{\\small\\textit{" + m.group(1) + "}}" if m else s
            continue
        m = re.match(r"\\noindent\\textsuperscript\{(\d+)\}(.+)", s)
        if m:
            verses.append("\\sverse{" + m.group(1) + "}{" + m.group(2).strip() + "}")
            continue
        if verses:
            verses[-1] = verses[-1] + " " + s
        else:
            verses.append(s + r"\par")

    result = "\n".join(pre).rstrip()
    if ref_line:
        result += ("\n" if result else "") + ref_line
    if verses:
        result += "\n\\begin{scripture}\n" + "\n".join(verses) + "\n\\end{scripture}"
    if post:
        result += "\n" + "\n".join(post)
    return result
