"""Helper utility functions for Rubric."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` so the file is never left half-written.

    A crash, a full disk, or an exception partway through a plain
    ``open(path, "w")`` truncates the existing file and loses its contents —
    which for a service file means losing the user's work. Writing to a temp
    file in the same directory, flushing it to disk, and renaming over the
    target makes the swap atomic: a reader sees either the complete old file
    or the complete new one, never a truncated hybrid.

    The temp file goes beside the target, not in /tmp, because ``os.replace``
    is only atomic within a single filesystem.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def flatpak_git_prefix() -> list[str]:
    """Return the git command prefix, routed through the host when sandboxed."""
    return ["flatpak-spawn", "--host", "git"] if Path("/.flatpak-info").exists() else ["git"]


def git_no_sign_args() -> list[str]:
    """Extra `-c` args that make one git invocation skip commit signing.

    Rubric's commits (and the merge commit `pull` can create) run from a
    background thread with no terminal attached — if the user's global git
    config has `commit.gpgsign` on, git tries to launch an interactive
    prompt to unlock the signing key, which can't work headless, and the
    whole sync fails with a raw gpg/pinentry error ("Inappropriate ioctl
    for device"). This overrides signing for Rubric's own git invocations
    only, leaving the global config — and commits made by hand — untouched.
    """
    return ["-c", "commit.gpgsign=false"]


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
