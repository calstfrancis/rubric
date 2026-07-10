"""Helper utility functions for Rubric."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def flatpak_git_prefix() -> list[str]:
    """Return the git command prefix, routed through the host when sandboxed."""
    return ["flatpak-spawn", "--host", "git"] if Path("/.flatpak-info").exists() else ["git"]


@contextlib.contextmanager
def git_credential_args(token: str | None):
    """Yields extra `-c` args that inject a short-lived GitHub credential for
    one git invocation (via a mode-0600 credential-store file under
    ~/.cache/rubric, deleted when the context exits), or [] if token is None.

    A file rather than an env var, because under a flatpak sandbox git runs
    via `flatpak-spawn --host`, which does not forward the caller's
    environment — but ~/.cache/rubric resolves to the same path on both
    sides since the sandbox has --filesystem=home.
    """
    if not token:
        yield []
        return
    cache_dir = Path.home() / ".cache/rubric"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=".git-cred-", dir=str(cache_dir))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(f"https://x-access-token:{token}@github.com\n")
        yield ["-c", "credential.helper=", "-c", f"credential.helper=store --file={path}"]
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


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
