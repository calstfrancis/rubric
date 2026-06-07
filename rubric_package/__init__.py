"""
Rubric - A GNOME-native worship service planning tool.

This package provides the core functionality for the Rubric application,
including data models, Typst export, and utility functions.
"""

__version__ = "0.12"

from .models.config import Config, get_palette, SECTIONS
from .models.service import ServiceItem, SectionDivider, entry_from_dict
from .utils.typst import typst_escape, note_for_typst, passage_to_typst
from .utils.colors import section_colour, hex_to_rgb
from .utils.helpers import is_hymn_element

__all__ = [
    "Config",
    "get_palette",
    "SECTIONS",
    "ServiceItem",
    "SectionDivider",
    "entry_from_dict",
    "typst_escape",
    "note_for_typst",
    "passage_to_typst",
    "section_colour",
    "hex_to_rgb",
    "is_hymn_element",
]
