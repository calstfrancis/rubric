# Rubric v0.15.1

Install with pipx (recommended):

```bash
pipx install --system-site-packages rubric-liturgy
```

Or download a native package below (see Assets).

---

### What's new

**Manuscript preview** — the preview panel now has a Bulletin | Manuscript toggle. Switch to Manuscript to see the full leader copy (with leader-note blocks) compiled as a PDF, without leaving Rubric.

**Delete key fixed** — pressing Delete while typing in any text field no longer accidentally removes the selected service element. The accelerator now checks for focus before acting.

**Preview scroll preserved** — the HTML bulletin preview restores your scroll position after every recompile. The PDF preview reloads in-place rather than resetting to the top of the document.

**Typst markup works in notes** — `_italic_`, `*bold*`, and headings entered in the element content editor now render correctly in compiled output. Previously, underscores and other Typst markup characters were being escaped, producing literal `\_italic\_`.

**Heading hierarchy fixed** — `=` is now the large centred section heading, `==` is the element heading with a thin rule, and `===` is a smaller sub-heading. Section dividers and item names in the bulletin and manuscript are generated at the correct levels.

---

### Install from package

**Debian/Ubuntu (.deb):**
```bash
sudo apt install ./rubric-liturgy_0.15.1_all.deb
```

**openSUSE (.rpm):**
```bash
sudo zypper install ./rubric-liturgy-0.15.1-1.noarch.rpm
```

**Fedora (.rpm):**
```bash
sudo dnf install ./rubric-liturgy-0.15.1-1.noarch.rpm
```

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
