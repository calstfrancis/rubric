# Rubric v0.15.3

Install with pipx (recommended):

```bash
pipx install --system-site-packages rubric-liturgy
```

Or download a native package below (see Assets).

---

### What's new

**Flatpak: git sync now works** — `git` is not available in the GNOME Platform sandbox. Rubric now routes all git operations through `flatpak-spawn --host` when running as a flatpak, so commit, push, and pull all work correctly.

---

### Also in 0.15.2

**Flatpak: PDF preview and export fixed** — the bundled Typst binary was installed to a path not on `$PATH`, silently breaking all PDF compilation in the flatpak. Moved to `/app/bin/typst` so it is found correctly.

---

### Install from package

**Debian/Ubuntu (.deb):**
```bash
sudo apt install ./rubric-liturgy_0.15.3_all.deb
```

**openSUSE (.rpm):**
```bash
sudo zypper install ./rubric-liturgy-0.15.3-1.noarch.rpm
```

**Fedora (.rpm):**
```bash
sudo dnf install ./rubric-liturgy-0.15.3-1.noarch.rpm
```

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
