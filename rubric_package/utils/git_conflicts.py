"""Interactive git merge-conflict resolution for non-technical users.

Rubric's sync data is one JSON `.liturgy` file per service, so a real merge
conflict almost always means "this file was edited on two computers" rather
than something needing a textual three-way merge. Instead of dropping the
user into a terminal, this walks them through each conflicted file with a
plain-language choice: keep mine, keep theirs, or keep both (saving the
other computer's version alongside so nothing is lost).

Deliberately paired with a plain `git pull` (merge), not `git pull --rebase`
— during a rebase, git's "ours"/"theirs" refer to the upstream commit and the
replayed local commit respectively (the reverse of the usual meaning), which
would make "Keep mine" silently keep the *other* computer's version. A plain
merge keeps "ours" = local and "theirs" = remote, matching what a user
reading "Keep mine" / "Keep theirs" would expect.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from gi.repository import Adw

from rubric_package.utils.helpers import flatpak_git_prefix

_GIT = flatpak_git_prefix()


def list_conflicted_files(repo: str) -> list[str]:
    """Paths (relative to repo) still unmerged, per git's index — the
    authoritative signal that a pull/merge left real conflicts, independent
    of how git happened to word the error on stdout/stderr."""
    r = subprocess.run(_GIT + ["-C", repo, "diff", "--name-only", "--diff-filter=U"],
                        capture_output=True, text=True, timeout=10)
    return [line for line in r.stdout.splitlines() if line.strip()]


def abort_merge(repo: str) -> None:
    subprocess.run(_GIT + ["-C", repo, "merge", "--abort"], capture_output=True, timeout=10)


def _other_computer_name(rel_path: str) -> str:
    p = Path(rel_path)
    return str(p.with_name(f"{p.stem} (from other computer){p.suffix}"))


def _apply_resolution(repo: str, rel_path: str, choice: str) -> None:
    if choice in ("mine", "both"):
        subprocess.run(_GIT + ["-C", repo, "checkout", "--ours", "--", rel_path],
                        capture_output=True, timeout=10, check=True)
    elif choice == "theirs":
        subprocess.run(_GIT + ["-C", repo, "checkout", "--theirs", "--", rel_path],
                        capture_output=True, timeout=10, check=True)

    if choice == "both":
        # Stage 3 in a merge conflict is "theirs" (the remote side).
        theirs = subprocess.run(_GIT + ["-C", repo, "show", f":3:{rel_path}"],
                                 capture_output=True, timeout=10)
        if theirs.returncode == 0:
            dest = Path(repo) / _other_computer_name(rel_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(theirs.stdout)
            subprocess.run(_GIT + ["-C", repo, "add", "--", str(dest.relative_to(repo))],
                            capture_output=True, timeout=10, check=True)

    subprocess.run(_GIT + ["-C", repo, "add", "--", rel_path],
                    capture_output=True, timeout=10, check=True)


def resolve_conflicts_interactive(parent, repo: str, on_done: Callable[[bool], None]) -> None:
    """Must be called on the GTK main thread. Shows one dialog per conflicted
    file, then completes the merge. Calls on_done(True) once the merge is
    committed and ready to push, or on_done(False) if the user cancelled or
    resolution failed (merge is aborted either way, leaving the repo clean)."""
    files = list_conflicted_files(repo)
    if not files:
        on_done(True)
        return
    _resolve_next(parent, repo, files, 0, on_done)


def _resolve_next(parent, repo: str, files: list[str], idx: int, on_done: Callable[[bool], None]) -> None:
    if idx >= len(files):
        _finish_merge(parent, repo, on_done)
        return

    rel_path = files[idx]
    progress = f" ({idx + 1} of {len(files)})" if len(files) > 1 else ""
    dlg = Adw.MessageDialog(
        transient_for=parent,
        heading=f"Conflicting changes in “{rel_path}”{progress}",
        body=("This file was edited on two computers since they last synced.\n\n"
              "Keep mine — use your local version\n"
              "Keep theirs — use the version from the other computer\n"
              "Keep both — keep yours here, and save the other computer's "
              "version as a separate file so nothing is lost"),
    )
    dlg.add_response("cancel", "Stop Syncing")
    dlg.add_response("mine",   "Keep Mine")
    dlg.add_response("theirs", "Keep Theirs")
    dlg.add_response("both",   "Keep Both")
    dlg.set_response_appearance("both", Adw.ResponseAppearance.SUGGESTED)
    dlg.set_default_response("both")
    dlg.set_close_response("cancel")

    def on_resp(_d, response):
        if response == "cancel":
            abort_merge(repo)
            on_done(False)
            return
        try:
            _apply_resolution(repo, rel_path, response)
        except subprocess.CalledProcessError as e:
            abort_merge(repo)
            err = Adw.MessageDialog(
                transient_for=parent, heading="Couldn't resolve that conflict",
                body=f"“{rel_path}”: {e}\n\n"
                     "Syncing was cancelled; nothing was changed.")
            err.add_response("ok", "OK"); err.present()
            on_done(False)
            return
        _resolve_next(parent, repo, files, idx + 1, on_done)

    dlg.connect("response", on_resp)
    dlg.present()


def _finish_merge(parent, repo: str, on_done: Callable[[bool], None]) -> None:
    r = subprocess.run(_GIT + ["-C", repo, "commit", "--no-edit"],
                        capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        abort_merge(repo)
        err = Adw.MessageDialog(
            transient_for=parent, heading="Couldn't complete sync",
            body=(r.stderr or r.stdout or "Unknown error").strip()[:400])
        err.add_response("ok", "OK"); err.present()
        on_done(False)
        return
    on_done(True)
