"""
Rubric - A GNOME-native worship service planning tool.

This package provides the core functionality for the Rubric application,
including data models, LaTeX export, and utility functions.
"""

__version__ = "0.12"

from .models.config import Config, get_palette, SECTIONS, DEFAULT_PREAMBLE
from .models.service import ServiceItem, SectionDivider, entry_from_dict
from .utils.latex import latex_escape, note_for_latex, passage_to_latex, migrate_scripture_note
from .utils.colors import section_colour, hex_to_rgb
from .utils.helpers import is_hymn_element

__all__ = [
    "Config",
    "get_palette",
    "SECTIONS",
    "DEFAULT_PREAMBLE",
    "ServiceItem",
    "SectionDivider",
    "entry_from_dict",
    "latex_escape",
    "note_for_latex",
    "passage_to_latex",
    "migrate_scripture_note",
    "section_colour",
    "hex_to_rgb",
    "is_hymn_element",
]
