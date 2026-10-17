"""Headless git sync engine for Rubric's GitHub backup.

Everything here is GTK-free and blocking — call it from a worker thread.
The UI layer (rubric.py, preferences_window.py) only decides how to present
the outcome; the git behaviour lives in one place so the toolbar Backup
button, "Get Latest", the periodic backup and the pull-on-startup all agree.

Deliberate choices, each of which fixed a way "just run `git pull`" fails
for someone who has never opened a terminal:

* `--no-rebase` — modern git refuses a bare `pull` on diverged branches
  ("Need to specify how to reconcile divergent branches"), and a user's
  global `pull.rebase=true` would flip "ours"/"theirs" under the
  Keep Mine / Keep Theirs dialogs (see git_conflicts.py).
* `--no-edit` — never open an editor for the merge commit.
* `--allow-unrelated-histories` — connecting a folder to a GitHub repo that
  was created with a README/licence has no common ancestor with the local
  history; for one-file-per-service data, merging them is exactly right.
* Local changes are committed *before* pulling, so a dirty tree can never
  make the pull refuse with "local changes would be overwritten".
* A half-finished merge from an earlier session is picked up, not left to
  wedge every later sync.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from rubric_package.utils.helpers import flatpak_git_prefix, git_no_sign_args
from rubric_package.utils.git_conflicts import list_conflicted_files, abort_merge

_GIT = flatpak_git_prefix()

# Outcomes of pull()
OK = "ok"                  # pulled (or nothing to pull); `changed` says which
CONFLICT = "conflict"      # merge stopped on conflicted files; resolve then finish
NO_REMOTE = "no_remote"    # no remote configured / remote branch doesn't exist yet
AUTH = "auth"              # credentials rejected
NETWORK = "network"        # couldn't reach GitHub
ERROR = "error"            # anything else; `message` has git's words


@dataclass
class PullResult:
    status: str
    changed: bool = False          # HEAD moved, i.e. files on disk may differ
    message: str = ""


def _git(repo: str, *args: str, cred=(), timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(_GIT + ["-C", repo, *cred, *args],
                          capture_output=True, text=True, timeout=timeout)


def _head(repo: str) -> str:
    r = _git(repo, "rev-parse", "-q", "--verify", "HEAD", timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def merge_in_progress(repo: str) -> bool:
    r = _git(repo, "rev-parse", "-q", "--git-path", "MERGE_HEAD", timeout=10)
    p = r.stdout.strip()
    if not p:
        return False
    path = Path(p) if Path(p).is_absolute() else Path(repo) / p
    return path.exists()


def has_remote(repo: str) -> bool:
    return bool(_git(repo, "remote", timeout=5).stdout.strip())


def commit_local(repo: str, message: str) -> tuple[bool, str]:
    """Stage everything and commit if there's anything to commit.
    Returns (ok, error_text)."""
    if merge_in_progress(repo):
        return True, ""            # can't commit mid-merge; finish_merge handles it
    add = _git(repo, "add", "-A", timeout=20)
    if add.returncode != 0:
        return False, (add.stderr or "git add failed").strip()
    if not _git(repo, "status", "--porcelain", timeout=10).stdout.strip():
        return True, ""
    c = _git(repo, *git_no_sign_args(), "commit", "-m", message, timeout=20)
    if c.returncode != 0:
        return False, (c.stderr or c.stdout or "git commit failed").strip()
    return True, ""


def _classify(out: str) -> str:
    low = out.lower()
    if any(k in low for k in ("permission denied", "authentication failed", "invalid username",
                              "could not read username", "returned error: 403")):
        return AUTH
    if any(k in low for k in ("could not resolve host", "network is unreachable", "timed out",
                              "connection refused", "unable to access")):
        return NETWORK
    if any(k in low for k in ("no tracking information", "no such ref", "couldn't find remote ref",
                              "no such remote")):
        return NO_REMOTE
    return ERROR


def pull(repo: str, cred=()) -> PullResult:
    """Merge the remote's changes into the local branch. Commit local work
    first (see commit_local). Never leaves the repo half-merged *unless* the
    result is CONFLICT, in which case the caller must resolve or abort."""
    if merge_in_progress(repo):
        return PullResult(CONFLICT) if list_conflicted_files(repo) else finish_merge(repo)

    if not has_remote(repo):
        return PullResult(NO_REMOTE)

    before = _head(repo)
    # A freshly connected folder has no upstream yet; name the remote branch
    # explicitly so its existing files still get merged in.
    target: list[str] = []
    if _git(repo, "rev-parse", "--abbrev-ref", "@{u}", timeout=10).returncode != 0:
        branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD", timeout=10).stdout.strip()
        if branch and branch != "HEAD":
            target = ["origin", branch]
    r = _git(repo, *git_no_sign_args(), "pull", "--no-rebase", "--no-edit",
             "--allow-unrelated-histories", *target, cred=cred, timeout=60)
    out = (r.stdout + r.stderr).strip()
    if r.returncode == 0:
        return PullResult(OK, changed=_head(repo) != before, message=out)
    if list_conflicted_files(repo):
        return PullResult(CONFLICT, message=out)
    abort_merge(repo)               # no-op if nothing to abort
    return PullResult(_classify(out), message=out)


def finish_merge(repo: str) -> PullResult:
    """Commit a merge whose conflicts have all been resolved."""
    before = _head(repo)
    r = _git(repo, *git_no_sign_args(), "commit", "--no-edit", timeout=20)
    if r.returncode != 0:
        abort_merge(repo)
        return PullResult(ERROR, message=(r.stderr or r.stdout or "merge commit failed").strip())
    return PullResult(OK, changed=_head(repo) != before)


def push(repo: str, cred=()) -> PullResult:
    """Push; if the remote moved since our pull, pull once more and retry.
    Returns OK, CONFLICT (second pull conflicted), or a failure status."""
    for attempt in range(2):
        r = _git(repo, "push", cred=cred, timeout=60)
        if r.returncode != 0:
            low = (r.stderr or "").lower()
            if "no upstream" in low or "set-upstream" in low or "set the upstream" in low:
                r = _git(repo, "push", "--set-upstream", "origin", "HEAD", cred=cred, timeout=60)
        if r.returncode == 0:
            return PullResult(OK)
        out = (r.stderr or r.stdout or "").strip()
        low = out.lower()
        rejected = "rejected" in low or "non-fast-forward" in low or "fetch first" in low
        if rejected and attempt == 0:
            p = pull(repo, cred)
            if p.status != OK:
                return p
            continue
        if "repository not found" in low:
            return PullResult(ERROR, message="Repository not found on GitHub.\n\n"
                                             "Check the URL in Preferences → GitHub.")
        return PullResult(_classify(out), message=out)
    return PullResult(ERROR, message="Push kept being rejected; try again in a moment.")
