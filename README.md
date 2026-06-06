# Rubric

[![Tests](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml/badge.svg)](https://github.com/calstfrancis/rubric/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/rubric-liturgy)](https://pypi.org/project/rubric-liturgy/)

A GNOME-native worship service planning tool for United Church of Canada ministry.

Rubric integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and export options for bulletin production.

---

## Features

- **Simple mode** (on by default) — hides LaTeX, GitHub sync, CSV export, snippets, responsive reading, and the LaTeX preamble preference. All features remain accessible when turned off. Toggle in **Preferences → View → Simple mode**.
- **RCL integration** — lectionary readings, liturgical colour, and season for any Sunday; weekday services default to the coming Sunday with a stepper
- **Lectionary year tracker** — persistent Year A/B/C and season indicator in the header, updated daily
- **Hymn suggestions** — season and Proper-specific suggestions (Propers 4–29) from VU, MV, and LUS; left-click to view on Hymnary.org, right-click to inject into the selected element
- **Hymn lookup** — type `VU 16` or `MV 120` to fetch the title from Hymnary.org; optional inline Hymnary preview via WebKit
- **Bible viewer** — fetch passages in WEB, KJV, ASV, or ESV (ESV requires a free API key from api.esv.org)
- **HTML export** — generates a clean, print-ready HTML file and opens it in the browser; use File → Print for a PDF without LaTeX
- **Congregational bulletin export**
  - **Simple mode** — HTML bulletin opens in the browser (no LaTeX required)
  - **Advanced mode** — LaTeX-compiled PDF for print or digital
    - **Print (booklet)** — `memoir` class, half-letter (5.5 × 8.5 in), fold for saddle-stitch
    - **Digital (screen PDF)** — `extarticle`, full letter, colour hyperlinks
- **Per-element bulletin toggle** — the 📋 button marks each element shown or hidden in the bulletin independently of the leader copy
- **Bulletin preferences** — church name, address, service time, website, email, phone, welcome line, accessibility note, mission statement, staff/contact list, and announcements — all in **Preferences → Bulletin**
- **Announcement expiry** — each announcement carries an optional `YYYY-MM-DD` expiry date; expired announcements are omitted automatically
- **Past Liturgies archive** — browse every saved service in a read-only viewer; insert any past element's text into the current service with one click
- **Element Library** — searchable database of every element from every saved service
- **Bulletin preview panel** — live preview of the congregational bulletin as you edit; popout to a floating window
- **Service Planner** — scans the `liturgy/` folder and lists all services grouped into Upcoming and Past
- **GitHub repository sync** — push/pull services to a GitHub repository with one click
- **Repository-aware save paths** — Save As, LaTeX export, and bulletin export default to the right subfolder when a repository is configured
- **Scripture translation selector** — choose WEB, KJV, ASV, or ESV in **Preferences → Scripture**
- **Undo / Redo** — Ctrl+Z and Ctrl+Shift+Z
- **LaTeX export** — `extarticle`, two-column layout per liturgical movement, Junicode font, proper scripture environment (advanced mode)
- **PDF compilation** — one-click xelatex compilation from within the app (advanced mode)
- **Snippets library** — reusable liturgical texts (advanced mode)
- **Responsive reading builder** — L:/P: syntax generates formatted LaTeX (advanced mode)
- **CSV export** — for sharing with musicians and AV teams (advanced mode)

---

## Requirements

- Python 3.10+
- GTK4 + libadwaita + python3-gobject (system packages)

**openSUSE / Leap / Tumbleweed:**
```bash
sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
```

**Ubuntu / Debian:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

**Fedora:**
```bash
sudo dnf install python3-gobject gtk4 libadwaita
```

LaTeX (xelatex + Junicode + `memoir` package) is only needed for PDF compilation and the advanced bulletin export. In simple mode, HTML export covers all bulletin and service order needs with no TeX Live required.

---

## Installation

### pipx (recommended)

[pipx](https://pipx.pypa.io) installs Rubric into an isolated environment and puts the `rubric` command on your PATH. Because Rubric uses system GTK libraries, pass `--system-site-packages`:

```bash
pipx install --system-site-packages rubric-liturgy
```

To update later:

```bash
pipx upgrade rubric-liturgy
```

### pip

```bash
pip install --user rubric-liturgy
```

Make sure `~/.local/bin` is on your PATH (`echo $PATH`). Add it permanently with:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Debian/Ubuntu .deb package

Download `rubric-liturgy_<version>_all.deb` from the [latest release](https://github.com/calstfrancis/rubric/releases/latest) and install:

```bash
sudo apt install ./rubric-liturgy_*.deb
```

This installs system-wide to `/usr/share/rubric/` and registers the `.desktop` entry, icons, MIME type, and AppStream metainfo automatically.

### openSUSE / Fedora RPM package

Download `rubric-liturgy-<version>-1.noarch.rpm` from the [latest release](https://github.com/calstfrancis/rubric/releases/latest) and install:

```bash
# openSUSE
sudo zypper install ./rubric-liturgy-*.noarch.rpm

# Fedora
sudo dnf install ./rubric-liturgy-*.noarch.rpm
```

### git clone (development / manual install)

```bash
git clone https://github.com/calstfrancis/rubric.git
cd rubric
bash install.sh
```

The install script copies app files to `~/.local/share/rubric/`, creates a launcher at `~/.local/bin/rubric`, installs the `.desktop` entry and icons, and registers the `.liturgy` MIME type.

---

## Usage

```bash
rubric
```

Or search for **Rubric** in GNOME Shell or your desktop launcher.

On first launch, a welcome wizard offers three starting points: today's lectionary, a blank service, or a guided tour.

---

## File format

Service files use the `.liturgy` extension (JSON). They store the service title, date, ordered elements with notes and leader assignments, and the path to the linked `.tex` export file.

---

## Running tests

```bash
python3 -m unittest test_rcl_data test_bible_api -v
```

---

## Project structure

```
rubric.py              Main application
rcl_data.py            RCL lectionary database and calendar logic
hymn_lookup.py         Hymnary.org title fetcher (VU, MV, LUS)
hymn_suggestions.py    Season and Proper-specific hymn suggestions
bible_api.py           Bible passage fetcher (WEB, KJV, ASV, ESV)
snippets.py            Default liturgical text snippets
observances.py         Liturgical calendar and observances intelligence
rubric_package/        Packaged models, utils, exporters, and data
install.sh             Manual install script (git clone path)
HELP.md                User guide
FAQ.md                 Frequently asked questions
CHANGELOG.md           Version history
RELEASING.md           How to cut a release
```

---

## Contributing

Contributions welcome — bug reports, hymn suggestion additions, and UCC-specific liturgical content especially so.

Please open an issue before starting significant work.

---

## Acknowledgements

- Lectionary data from the [Revised Common Lectionary](https://lectionary.library.vanderbilt.edu/)
- Hymn data from [Hymnary.org](https://hymnary.org/)
- Bible text from the [World English Bible](https://worldenglish.bible/) (public domain), [King James Version](https://www.kingjamesbibleonline.org/) (public domain), [American Standard Version](https://www.biblegateway.com/versions/American-Standard-Version-ASV-Bible/) (public domain), and [ESV](https://api.esv.org/) (free ministry API)
- Built with [GTK4](https://gtk.org/) and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)

---

## License

GPL-3.0 — see [LICENSE](LICENSE)

---

*Developed at Atlantic School of Theology, Halifax, Nova Scotia.*
