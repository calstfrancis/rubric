"""Utility functions for Rubric."""

from .typst import typst_escape, note_for_typst, passage_to_typst, strip_typst_for_html, strip_typst_plain
from .colors import section_colour, hex_to_rgb
from .helpers import is_hymn_element, HYMN_KEYWORDS
from .rich_typst import (
    TAG_BOLD, TAG_ITALIC, TAG_H1, TAG_H2, TAG_H3, TAG_LEADER, TAG_BULLET, TAG_ORDERED,
    ensure_tags, process_inline, typst_to_tags, tags_to_typst,
)

__all__ = [
    "typst_escape",
    "note_for_typst",
    "passage_to_typst",
    "strip_typst_for_html",
    "strip_typst_plain",
    "section_colour",
    "hex_to_rgb",
    "is_hymn_element",
    "HYMN_KEYWORDS",
    "TAG_BOLD", "TAG_ITALIC", "TAG_H1", "TAG_H2", "TAG_H3",
    "TAG_LEADER", "TAG_BULLET", "TAG_ORDERED",
    "ensure_tags", "process_inline", "typst_to_tags", "tags_to_typst",
]
