# Rubric v0.14.4

Install with pipx (recommended):

```bash
pipx install --system-site-packages rubric-liturgy
```

Or download a native package below (see Assets).

---

### What's new

**deb package** (`build-deb.sh`) — builds a native Debian/Ubuntu `.deb` for system-wide installation using only standard Linux tools; no dpkg-deb required. Installs to `/usr/share/rubric/` with a launcher at `/usr/bin/rubric` and full desktop integration.

**RPM package** (`build-rpm.sh`) — builds a native `.rpm` for openSUSE and Fedora using `rpmbuild`. Distro-conditional dependencies and proper `%post`/`%postun` hooks for MIME, desktop, and icon cache updates.

---

### Install from package

**Debian/Ubuntu (.deb):**
```bash
sudo apt install ./rubric-liturgy_0.14.4_all.deb
```

**openSUSE (.rpm):**
```bash
sudo zypper install ./rubric-liturgy-0.14.4-1.noarch.rpm
```

**Fedora (.rpm):**
```bash
sudo dnf install ./rubric-liturgy-0.14.4-1.noarch.rpm
```

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
