"""Color utility functions for Rubric.

Section colours are a *derived family*, not a bag of unrelated hues: one hue
rotation at roughly constant lightness and chroma, with a parallel set lifted
for dark backgrounds. Nothing here is written into a stylesheet as a literal —
:func:`section_css` emits the scheme-appropriate rules at runtime so light,
dark, and accent changes all stay correct.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.config import Config


# Section palette — one hue rotation, even lightness. Index order is the order
# sections appear in the palette config, so consecutive sections stay distinct.
SECTION_COLORS = [
    "#3F6B57",  # green      — typically Gathering
    "#4A5E8C",  # blue       — typically Word
    "#8A5A2E",  # amber      — typically Response
    "#6B4A7A",  # violet     — typically Sending
    "#2F6B6B",  # teal
    "#8C4A55",  # rose
    "#5C6B33",  # olive
    "#7A4F2A",  # umber
]

# Same family, lifted for dark grounds (higher lightness, lower chroma).
SECTION_COLORS_DARK = [
    "#6FA98A",
    "#8098CE",
    "#C89A5E",
    "#AC8ABB",
    "#63A8A8",
    "#C88A93",
    "#9AAD66",
    "#BE8F63",
]

# Neutral fallback for sections that aren't in the palette.
SECTION_GRAY = "#888780"
SECTION_GRAY_DARK = "#9A9CA5"

# The colour the app is named for. Reserved for rubrics (liturgical
# instructions) and unsaved state — never for chrome or destructive actions.
RUBRIC_RED = "#A81F16"
RUBRIC_RED_DARK = "#E2685A"

# Running-time feedback in the section headers.
TIME_OVER = "#A81F16"
TIME_OVER_DARK = "#E2685A"
TIME_OK = "#3F6B57"
TIME_OK_DARK = "#6FA98A"


def is_dark_scheme() -> bool:
    """True when libadwaita is currently rendering a dark colour scheme.

    Falls back to light when libadwaita isn't available (headless tests).
    """
    try:
        import gi

        gi.require_version("Adw", "1")
        from gi.repository import Adw

        return bool(Adw.StyleManager.get_default().get_dark())
    except Exception:
        return False


def section_colour(section: str, config: Config | None = None,
                   dark: bool | None = None) -> str:
    """
    Return a color for the given section.

    Args:
        section: Section name
        config: Optional config object for custom palette
        dark: Force the dark or light variant; resolved from libadwaita when None

    Returns:
        Hex color code
    """
    # Import here to avoid circular imports
    from ..models.config import get_palette

    if dark is None:
        dark = is_dark_scheme()
    table = SECTION_COLORS_DARK if dark else SECTION_COLORS
    fallback = SECTION_GRAY_DARK if dark else SECTION_GRAY

    palette = get_palette()
    secs = [s for s, _ in palette]
    try:
        return table[secs.index(section) % len(table)]
    except ValueError:
        pass

    # Not one of the configured sections — a renamed or ad-hoc divider. Derive a
    # stable colour from the name rather than dropping to grey: every section in
    # a service should read as a section, and a real service is full of dividers
    # that don't happen to match the default palette's wording.
    name = (section or "").strip()
    if not name:
        return fallback
    h = 0
    for b in name.encode("utf-8"):
        h = (h * 31 + b) & 0xFFFFFFFF
    return table[h % len(table)]


def rubric_red(dark: bool | None = None) -> str:
    """The rubric red for the current colour scheme."""
    if dark is None:
        dark = is_dark_scheme()
    return RUBRIC_RED_DARK if dark else RUBRIC_RED


def time_colours(dark: bool | None = None) -> tuple[str, str]:
    """(over-budget, within-budget) colours for running-time labels."""
    if dark is None:
        dark = is_dark_scheme()
    if dark:
        return TIME_OVER_DARK, TIME_OK_DARK
    return TIME_OVER, TIME_OK


# Row cue dots: the element's kind, said in colour rather than an icon.
CUE_MUSIC = SECTION_COLORS[0]
CUE_MUSIC_DARK = SECTION_COLORS_DARK[0]


def section_css(dark: bool | None = None) -> str:
    """Scheme-dependent CSS: section accents and the rubric-note tint.

    Regenerated whenever the colour scheme changes, so no section colour is
    ever a literal in a static stylesheet.
    """
    if dark is None:
        dark = is_dark_scheme()
    table = SECTION_COLORS_DARK if dark else SECTION_COLORS
    gray = SECTION_GRAY_DARK if dark else SECTION_GRAY
    red = RUBRIC_RED_DARK if dark else RUBRIC_RED

    music = CUE_MUSIC_DARK if dark else CUE_MUSIC
    rules = [
        f".cue-music {{ color: {music}; }}",
        f".cue-read {{ color: {red}; }}",
        f".rubric-note-editor {{ color: {red}; }}",
        f".rubric-red {{ color: {red}; }}",
        f".section-dot-gray {{ color: {gray}; }}",
    ]
    for i, hexval in enumerate(table):
        rules.append(f".section-dot-c{i} {{ color: {hexval}; }}")
    return "\n".join(rules) + "\n"


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """
    Convert hex color to RGB tuple with values 0-1.

    Args:
        hex_color: Hex color code (e.g., "#3F6B57")

    Returns:
        Tuple of (red, green, blue) floats in range 0-1
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16) / 255,
        int(hex_color[2:4], 16) / 255,
        int(hex_color[4:6], 16) / 255,
    )
