# Rubric v0.22.0 "Quiet Confluence"

Install via Flatpak:

```bash
flatpak remote-add --user calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
flatpak install calstfrancis io.github.calstfrancis.rubric
```

Already installed? Update with:

```bash
flatpak update io.github.calstfrancis.rubric
```

---

### What's new

**Rubric picks up your other computer's work on its own.** A few seconds after launch, Rubric quietly checks GitHub for anything backed up from another machine. The open service and the Services planner refresh themselves when something arrives, and a toast tells you.

**Backup and Get Latest stop tripping over git.** Backing up from two computers used to fail with git's "divergent branches" complaint once both had changed things; connecting to a GitHub repository that already had a README failed with "unrelated histories"; Get Latest refused when you had unsaved edits; and a backup that raced the other computer's reported a failure. All of those now just work. A merge left half-finished by an earlier session is finished instead of blocking every later sync, and a network outage is told apart from a sign-in problem.

A real conflict — the same service edited on two computers — still asks you, in plain words: keep mine, keep theirs, or keep both.

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
