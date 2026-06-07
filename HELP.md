# Rubric — User Guide

## Overview

Rubric is a GNOME-native application for planning worship services for the United Church of Canada. It integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and export to HTML or LaTeX for bulletin production.

Install via pipx (recommended):

```bash
pipx install --system-site-packages rubric-liturgy
```

See [README.md](README.md) for full installation instructions including system dependencies.

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
| Rich text content editor | ✓ | ✓ |
| Bulletin → HTML | ✓ | ✓ |
| Bulletin → PDF (Typst) | ✓ | ✓ |
| Bible viewer | ✓ | ✓ |
| Hymn lookup and suggestions | ✓ | ✓ |
| Service Planner | ✓ | ✓ |
| GitHub sync | — | ✓ |
| Snippets library | — | ✓ |
| Responsive reading builder | — | ✓ |
| CSV export | — | ✓ |

Toggle simple mode in **Preferences → View → Simple mode**. All keyboard shortcuts work regardless of mode.

---

## Header Bar

The header bar shows (left to right):
- **New / Open / Undo / Redo** buttons
- **Window title** (centre, click to open service info popover)
- **Lectionary year tracker** — coloured dot + "Year A · Advent" showing today's RCL year and season. Hover for the full week name.
- **GitHub sync button** (⟳) — push the current service to GitHub (advanced mode / GitHub configured)
- **Document icon** — quick Typst export (Ctrl+E) — saves and compiles the leader's order
- **Print icon** — compile bulletin to PDF via Typst (Ctrl+Shift+P)
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

### Content editor

Below the toolbar is the element content editor. It stores a single Typst string used for both the leader copy and the bulletin. Two editing modes:

- **Rich text mode** (default) — formatting toolbar with **B** (bold), **I** (italic), **H1/H2/H3** (headings), **•** (bullet list), **1.** (numbered list), and **Ldr** (leader note — grey box, omitted from the congregational bulletin). Keyboard shortcuts: Ctrl+B, Ctrl+I.
- **Typst mode** — raw Typst source editor (monospace, syntax-highlighted). Toggle with the **Typst** button at the top right.

Switching modes preserves content exactly. A small notice appears if you switch from Typst to rich text and the source contains markup outside the supported subset — those constructs are displayed as literal text (no data is lost).

**Leader notes** (the `#leader-note[…]` block, added with the **Ldr** button) appear in the leader copy but are stripped from the congregational bulletin automatically.

---

## Bible Viewer

Fetches passages in your chosen translation (WEB by default; set in **Preferences → Scripture**). Click **Insert scripture** to add a formatted `#scripture[…]` block to the selected element's content editor.

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

## Bulletin Preview Panel

Click the **bulletin preview button** in the header bar (or toggle via the menu) to open a live preview panel on the right side of the window. The preview updates automatically as you edit (debounced to avoid constant recompilation).

- **With typst installed** — compiles a real PDF in the background. A spinner appears while compiling; errors appear as a brief toast.
- **Without typst** — falls back to the HTML preview.
- **⚙ gear icon** in the preview header — quick access to Print/Digital mode toggle and the church name field without opening the full preferences dialog.
- **Popout button** — opens the preview in a separate floating window so you can see it alongside your editing.

---

## Bulletin Export

**Export Bulletin** (Ctrl+Shift+B) opens the export dialog. Choose one or more outputs:
- **Bulletin — print (booklet)** — Typst-compiled PDF, half-letter (5.5 × 8.5 in), fold for saddle-stitch
- **Bulletin — digital (screen)** — Typst-compiled PDF, full letter, colour hyperlinks
- **HTML** — opens in your browser; use File → Print to produce a PDF without Typst

All outputs filter to bulletin-visible elements only (controlled by the Bulletin toggle in the item toolbar). Active announcements are included; expired announcements are filtered automatically.

If Typst is not found, only HTML export is available.

---

## Service Planner

Hamburger menu → **Service Planner** (Ctrl+Shift+L). Scans the `liturgy/` subfolder of your repository (or any folder you choose) and lists all `.liturgy` files:
- **Upcoming** — services dated today or later
- **Past** — services with earlier dates

Click any row to open that service. Use **Refresh** to rescan after adding or moving files.

If no repository is configured, the planner asks you to choose a folder on first use.

---

## Past Liturgies

Hamburger menu → **Past Liturgies** (Ctrl+Shift+H). A read-only browser of every service you have saved and indexed. Use this to look back at past services without replacing what you're working on.

- Services are listed newest-first. Click any service row to expand it and read the full content.
- Each expanded service shows its elements grouped by section, with the full leader notes displayed in plain text (LaTeX formatting stripped for readability).
- **Open in editor** button on each service loads it into the main window (you will be asked to save or discard the current service first).
- **Insert** button on any element copies that element's notes into whichever element is currently selected in the service order.
- The **search bar** filters by service title, date, or element content across all indexed services.

Services are indexed automatically in the background when you save or open them. No manual indexing is required.

---

## Element Library

Hamburger menu → **Element Library** (Ctrl+Shift+K). A searchable database of every individual element from every service in your library.

- **Empty search** — browse by service. Click a service row to expand it and see its elements.
- **Type to search** — finds elements by name, notes, or leader across all services. Results are sorted newest-first.
- **Insert** button copies that element's leader notes into the currently selected element in the service order.

The Element Library and Past Liturgies are complementary: use Element Library when you remember what an element was called and want to pull its text; use Past Liturgies when you want to read through a whole service.

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

**℟** button or Ctrl+R (advanced mode). Prefix lines `L:` (Leader) or `P:` (People); unprefixed lines alternate automatically. Inserts formatted Typst into the element content editor.

---

## Typst Templates

Rubric exports bulletins and manuscripts as Typst (`.typ`) files compiled by the bundled `typst` binary.

### Editing templates

**Preferences → Typst Files** shows the four template files:
- **Bulletin — print/booklet** (`bulletin_print.typ`) — page size, margins, fonts for folded bulletins
- **Bulletin — digital/screen** (`bulletin_digital.typ`) — full-letter layout with coloured hyperlinks
- **Manuscript** (`manuscript.typ`) — leader copy layout
- **Shared functions** (`_shared.typ`) — Rubric's custom Typst functions (`#movement`, `#sverse`, `#scripture`, `#leader-note`, etc.)

Click **Edit…** to open the template in an in-app editor (with Typst syntax highlighting if GtkSourceView is installed). Click **Save override** to write your version to `~/.config/rubric/templates/`. Rubric checks that folder before the bundled copies, so your overrides persist across upgrades. Click **Reset to default** to remove your override and restore the bundled version.

### Custom Typst in element content

Switch any element to **Typst mode** (toggle button top-right of the content editor) to enter raw Typst. You can use any Typst function, not just the Rubric subset. Out-of-subset constructs are passed through to the compiled document unchanged — only the rich-text editor won't render them visually.

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
| Export LaTeX | Ctrl+E |
| Compile PDF | Ctrl+Shift+P |
| Export Bulletin | Ctrl+Shift+B |
| GitHub sync (push) | Ctrl+Shift+G |
| Service Planner | Ctrl+Shift+L |
| Past Liturgies | Ctrl+Shift+H |
| Element Library | Ctrl+Shift+K |
| Add custom element | Ctrl+Shift+N |
| Add divider | Ctrl+D |
| Move item up | Ctrl+↑ |
| Move item down | Ctrl+↓ |
| Responsive reading | Ctrl+R |
| Insert snippet | Ctrl+Shift+I |
| Scripture search focus | Ctrl+Shift+F |
| Preferences | Ctrl+, |
| Help | F1 |
