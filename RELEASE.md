# Rubric v0.15.0

Install with pipx (recommended):

```bash
pipx install --system-site-packages rubric-liturgy
```

Or download a native package below (see Assets).

---

### What's new

**Typst syntax highlighting** — the Typst mode editor now uses GtkSourceView with a bundled language definition. Headings, bold, italic, function calls, comments, math, labels, and Rubric-specific keywords are all highlighted. Falls back gracefully to plain monospace if GtkSourceView is not installed.

**In-app Typst template editor** (Preferences → Typst Files) — view and edit the four preamble templates (`bulletin_print`, `bulletin_digital`, `manuscript`, `_shared`) without leaving Rubric. Save creates a user override in `~/.config/rubric/templates/` that persists across upgrades; Reset restores the bundled default.

**Better compile error messages** — Typst stderr is now parsed into structured errors with line numbers. Toasts show "unclosed delimiter (line 42)" instead of a raw stderr dump.

**Typst binary bundled in packages** — the `.deb` and `.rpm` include the system `typst` binary at `/usr/share/rubric/bin/typst` so PDF compilation works out of the box on a clean install.

---

### Install from package

**Debian/Ubuntu (.deb):**
```bash
sudo apt install ./rubric-liturgy_0.15.0_all.deb
```

**openSUSE (.rpm):**
```bash
sudo zypper install ./rubric-liturgy-0.15.0-1.noarch.rpm
```

**Fedora (.rpm):**
```bash
sudo dnf install ./rubric-liturgy-0.15.0-1.noarch.rpm
```

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
