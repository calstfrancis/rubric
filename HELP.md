# Rubric — User Guide

## Overview

Rubric is a GNOME-native application for planning worship services for the United Church of Canada. It integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and export to HTML or LaTeX for bulletin production.

---

## First Launch

The first time Rubric opens, a welcome wizard appears with three choices:

- **Start with today's lectionary** — pre-fills a complete four-movement order (Gathering, Word, Response, Sending) with standard element names and injects this Sunday's RCL reading references into the relevant notes. The readings card, hymn suggestions, and observances row are all populated automatically.
- **Blank service** — opens a clean document so you can build from scratch.
- **Show me around** — opens the Help guide and starts the quickstart tip strip.

The wizard only appears once. Afterward, Rubric opens to whatever you last had open.

### Quickstart tip strip

After the wizard (or on "Show me around"), a dismissible banner appears below the readings card. It cycles through six short tips. Click **Next tip →** to advance; click **✕** to dismiss permanently. You can restart it any time from the hamburger menu → Help → Quickstart tips.

---

## Simple Mode vs. Advanced Mode

Rubric launches in **Simple mode** by default. This keeps the interface clean for everyday planning use — no LaTeX knowledge required.

| Feature | Simple mode | Advanced mode |
|---------|-------------|---------------|
| Service planning | ✓ | ✓ |
| HTML export | ✓ | ✓ |
| Bulletin → HTML | ✓ | ✓ |
| Bible viewer | ✓ | ✓ |
| Hymn lookup and suggestions | ✓ | ✓ |
| Service Planner | ✓ | ✓ |
| GitHub sync | ✓ | ✓ |
| LaTeX export | — | ✓ |
| PDF compilation | — | ✓ |
| Bulletin → PDF (LaTeX) | — | ✓ |
| Snippets library | — | ✓ |
| Responsive reading builder | — | ✓ |
| CSV export | — | ✓ |
| LaTeX preamble editor | — | ✓ |

Toggle simple mode in **Preferences → View → Simple mode**. All keyboard shortcuts work regardless of mode.

---

## Header Bar

The header bar shows (left to right):
- **New / Open / Undo / Redo** buttons
- **Window title** (centre, click to open service info popover)
- **Lectionary year tracker** — coloured dot + "Year A · Advent" showing today's RCL year and season. Hover for the full week name.
- **GitHub sync button** (⟳) — push the current service to GitHub (advanced mode / GitHub configured)
- **Document icon** — quick LaTeX export (Ctrl+E) — advanced mode only
- **Print icon** — compile to PDF via xelatex (Ctrl+Shift+P) — advanced mode only
- **Save** button
- **Hamburger menu**

---

## Service Info Popover

Click the window title to open. Contains:
- **Service title** — free text, appears in exports
- **Date picker** — drives the RCL readings, hymn suggestions, and the date in all export formats

---

## Lectionary Year Tracker

A persistent "Year B · Lent" indicator in the header shows the current RCL year and season based on today's date, independent of any selected service date. Useful context when planning ahead. Updates at midnight.

---

## Left Panel — Element Palette

Lists liturgical elements by section. **Double-click** to add at the current position. Customise in **Preferences → Palette**.

---

## Right Panel — Service Order

### Views
- **Flat list** (default): one scrollable list with section dividers
- **Tab view**: each divider becomes a tab. Toggle in **Preferences → View**. Right-click a tab to Rename or Delete.

### Adding elements
- Double-click palette item
- **＋ Custom…** (Ctrl+Shift+N)
- **＋ Divider** (Ctrl+D)

### Reordering
- Drag the **⠿** handle
- **Ctrl+↑ / Ctrl+↓**
- In tab mode: drag items between tabs

---

## Readings Card

When a date is set, shows:
- **Colour bar** — liturgical season colour
- **Season and week** (e.g. "Proper 12, Year A") alongside four reading buttons
- **Four reading buttons** — First Reading · Psalm · Epistle · Gospel. Click to open the Bible Viewer.
- **Observances row** — a compact row of labelled badges for feasts, commemorations, and seasonal observances relevant to the service date (see below).

### Weekday services
Weekday dates default to the next Sunday's readings with a ← → stepper. Useful for Thursday chapels.

### Observances row

The observances row appears automatically when there is something worth noting for the service date. Each badge shows a coloured type label and the observance name:

| Badge colour | Category | Examples |
|---|---|---|
| Gold | Feast | All Saints, Christmas, Easter Vigil |
| Violet | Saint | feast days of named saints |
| Teal | Ecumenical | Week of Prayer for Christian Unity, World Day of Prayer |
| Amber | Indigenous | Indigenous Sunday, Orange Shirt Day |
| Rose | Social Justice | International Women's Day, World AIDS Day, 16 Days of Activism |
| Green | Ecological | Earth Day, Earth Sunday, Season of Creation |
| Rainbow | Pride | Pride Month, Pride Sunday |
| Grey-blue | Remembrance | Remembrance Day, Remembrance Sunday |
| Purple | UCC | UCC-specific commemorations |

When the service date is a Sunday, observances falling on weekdays within that same week appear with a proximity note (e.g. "Orange Shirt Day · *this Wednesday*"). This helps you decide whether to acknowledge the observance on the preceding Sunday.

---

## Hymn Suggestions Strip

When a date is set, suggested hymns for the RCL week appear (VU, MV, LUS):
- **Left-click** a chip → opens inline Hymnary preview (if WebKit is installed) or browser
- **▶ button** → YouTube search
- **Right-click** a chip → injects `VU 16 — Mary, woman of the promise` into the **currently selected element's** Notes/Content

Select an element in the order list first, then right-click a chip — no new elements are created.

Suggestions are specific to the Proper (Propers 4–29) or season.

---

## Item Toolbar

Appears when any service element is selected. The toolbar has two rows:

**Row 1 — Assignment and bulletin**

| Field | Purpose |
|-------|---------|
| Leader | Name or role — exports right-aligned italic in headings |
| Bulletin | Toggle whether this element appears in the bulletin |

**Row 2 — Content actions**

| Field | Purpose |
|-------|---------|
| Scripture | Type any reference (e.g. `Ps 23`) and press Enter to open the Bible Viewer |
| Hymn | Type `VU 16` and press Enter to look up and inject the title (appears only for hymn-type elements) |
| Snippet | Insert a snippet (Ctrl+Shift+I) — advanced mode |
| Reading | Open the Responsive Reading builder (Ctrl+R) — advanced mode |

### Notes panel — Leader notes / Bulletin text

Below the toolbar, two tabs hold separate text areas:

- **Leader notes** — free-form text that exports to the leader copy (LaTeX/HTML). RCL reading references injected from a loaded file appear here. This is where you type sermon notes, prayers, responsive reading text, etc.
- **Bulletin text** — separate text that appears in the congregational bulletin in place of the leader notes (optional). Leave blank to use leader notes content in the bulletin.

Rubric always switches to **Leader notes** when you select an item, so injected content is never hidden.

---

## Bible Viewer

Fetches passages in your chosen translation (WEB by default; set in **Preferences → Scripture**). Click **Insert as LaTeX** to add a formatted `{scripture}` block to the selected element's Notes/Content.

### ESV
ESV requires a free API key from api.esv.org. Ministry and bulletin use is explicitly permitted by the ESV licence. Enter your key in **Preferences → Scripture**.

---

## Hymn Lookup

Select a hymn-type element, type `VU 16` (or `MV 120`, `LUS 5`) in the **Hymn #** field and press Enter. The title is fetched from Hymnary.org and prepended to Notes/Content as `VU 16 — Mary, woman of the promise`. Results are cached.

---

## HTML Export

Hamburger menu → **Export → Export HTML** (or Ctrl+Shift+H). Generates a clean, print-ready HTML file and opens it in your default browser. Use File → Print in the browser to produce a PDF without needing LaTeX.

The HTML export includes:
- Service title and date
- All sections and elements with their notes
- Scripture blocks formatted with verse numbers

---

## Bulletin Export

### Simple mode (default)
**Export Bulletin** (Ctrl+Shift+B) generates an HTML bulletin and opens it in your browser. Includes:
- Church name, service details, welcome line
- Order of service (bulletin-visible elements only — controlled by the 📋 button)
- Active announcements (expired ones are filtered automatically)
- Staff list, mission statement, accessibility note

Use File → Print in the browser to produce a print-ready PDF.

### Advanced mode
**Export Bulletin** opens the LaTeX bulletin dialog. Choose **Print (booklet)** or **Digital (screen)**:
- **Print/booklet** — `memoir` class, half-letter (5.5 × 8.5 in), fold for saddle-stitch
- **Digital/screen** — `extarticle`, full letter, colour hyperlinks

Both formats require TeX Live with xelatex and the `memoir` package.

---

## Service Planner

Hamburger menu → **Service Planner** (Ctrl+Shift+L). Scans the `liturgy/` subfolder of your repository (or any folder you choose) and lists all `.liturgy` files:
- **Upcoming** — services dated today or later
- **Past** — services with earlier dates

Click any row to open that service. Use **Refresh** to rescan after adding or moving files.

If no repository is configured, the planner asks you to choose a folder on first use.

---

## GitHub Sync

### Setup
1. Go to **Preferences → GitHub**.
2. Click **Browse** and choose a local folder for your repository.
3. Click **Set up** — creates `liturgy/`, `tex/`, `pdf/`, `bulletins/` subfolders, a `.gitignore`, and initialises a git repository.
4. Paste your GitHub repository URL into the **Remote URL** field and click **Connect**.

### Syncing
- **Push** (⟳ toolbar button or Ctrl+Shift+G) — saves the current service, commits it with an automatic message (`Service: Title – Date`), and pushes to GitHub. No commit message required.
- **Pull** — **Preferences → GitHub → Pull** downloads changes from GitHub. Pull before editing on a different machine.

### Repository-aware save paths
When a repository is configured:
- Save As defaults to `repo/liturgy/`
- Export LaTeX defaults to `repo/tex/`
- Bulletin export defaults to `repo/bulletins/`
- Compiled PDFs move automatically to `repo/pdf/` (service order) or `repo/bulletins/` (bulletin)

### Authentication
GitHub no longer accepts passwords. Use a Personal Access Token (PAT) or SSH keys. Store your PAT with `git credential-store` to avoid re-entering it.

---

## Snippets

**✂** button or Ctrl+Shift+I (advanced mode). Click any snippet to insert into Notes/Content.

Defaults: Land acknowledgement, Prayers of the People (full structure), Lord's Prayer (traditional and contemporary), Words of Assurance, Benediction, Words of Institution.

Manage in **Preferences → Snippets**.

---

## Responsive Reading Builder

**℟** button or Ctrl+R (advanced mode). Prefix lines `L:` (Leader) or `P:` (People); unprefixed lines alternate automatically. Inserts formatted LaTeX into Notes/Content.

---

## LaTeX Export

*Advanced mode only.*

### Quick export (Ctrl+E)
Click the document icon. First use opens a file chooser; the path is remembered. Subsequent presses overwrite immediately. Right-click to change or unlink.

### Structure
- `extarticle`, 12pt, 0.5in margins, Junicode font
- Each divider → new page, centred small-caps heading
- Each element → `\section*` with optional right-aligned leader name
- Two-column layout per movement (`multicol`)
- Scripture in `{scripture}` environment with hanging verse indent

### Compile to PDF (Ctrl+Shift+P)
Runs `xelatex` in a background thread. "Compiling PDF…" toast stays until done; success opens the PDF automatically. Helper files (`.log`, `.aux`, etc.) are cleaned up automatically.

---

## Exporting (other formats)

Hamburger menu → **Export**:
- **Export HTML…** — print-ready HTML for the service order
- **Export LaTeX…** — opens the file chooser (advanced mode)
- **Export plain text…** — section headings and element names
- **Export CSV…** — Section, Element, Leader, Hymn ref, Notes preview (advanced mode)

---

## Templates

**Save order as template…** in the hamburger menu. Give it a name. Notes/Content is saved; date is not.

Multiple templates → chooser on New service. One template → applied silently.

Manage in **Preferences → Templates**.

---

## Help

Hamburger menu → Help section: **Help** (F1), **FAQ**, **What's New**.

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New service | Ctrl+N |
| Open | Ctrl+O |
| Save | Ctrl+S |
| Save as | Ctrl+Shift+S |
| Undo | Ctrl+Z |
| Redo | Ctrl+Shift+Z |
| Export HTML | Ctrl+Shift+H |
| Export LaTeX | Ctrl+E |
| Compile PDF | Ctrl+Shift+P |
| Export Bulletin | Ctrl+Shift+B |
| GitHub sync (push) | Ctrl+Shift+G |
| Service Planner | Ctrl+Shift+L |
| Add custom element | Ctrl+Shift+N |
| Add divider | Ctrl+D |
| Move item up | Ctrl+↑ |
| Move item down | Ctrl+↓ |
| Responsive reading | Ctrl+R |
| Insert snippet | Ctrl+Shift+I |
| Scripture search focus | Ctrl+Shift+F |
| Preferences | Ctrl+, |
| Help | F1 |
