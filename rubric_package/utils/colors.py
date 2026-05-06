"""Color utility functions for Rubric."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.config import Config


# Default section colors (libadwaita-inspired palette)
SECTION_COLORS = [
    "#1D9E75",  # Green
    "#534AB7",  # Purple
    "#993C1D",  # Brown/Red
    "#185FA5",  # Blue
    "#B45309",  # Orange
    "#6B21A8",  # Dark Purple
    "#15803D",  # Dark Green
    "#B91C1C",  # Red
]


def section_colour(section: str, config: Config | None = None) -> str:
    """
    Return a color for the given section.

    Args:
        section: Section name
        config: Optional config object for custom palette

    Returns:
        Hex color code
    """
    # Import here to avoid circular imports
    from ..models.config import get_palette

    palette = get_palette()
    secs = [s for s, _ in palette]
    try:
        return SECTION_COLORS[secs.index(section) % len(SECTION_COLORS)]
    except ValueError:
        return "#888780"  # Gray fallback


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """
    Convert hex color to RGB tuple with values 0-1.

    Args:
        hex_color: Hex color code (e.g., "#1D9E75")

    Returns:
        Tuple of (red, green, blue) floats in range 0-1
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16) / 255,
        int(hex_color[2:4], 16) / 255,
        int(hex_color[4:6], 16) / 255,
    )
