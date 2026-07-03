"""Helper utility functions for Rubric."""

from __future__ import annotations

from pathlib import Path


def flatpak_git_prefix() -> list[str]:
    """Return the git command prefix, routed through the host when sandboxed."""
    return ["flatpak-spawn", "--host", "git"] if Path("/.flatpak-info").exists() else ["git"]


# Keywords to identify hymn-type elements
HYMN_KEYWORDS = {"hymn", "psalm", "sung", "song", "music", "anthem", "gloria"}


def is_hymn_element(name: str) -> bool:
    """
    Check if an element name indicates a hymn/song element.

    Args:
        name: Element name to check

    Returns:
        True if the element appears to be a hymn/song
    """
    return any(keyword in name.lower() for keyword in HYMN_KEYWORDS)
