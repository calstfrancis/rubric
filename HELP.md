# Rubric — User Guide

## Overview

Rubric is a GNOME-native application for planning worship services for the United Church of Canada. It integrates the Revised Common Lectionary, hymn lookup for Voices United, More Voices, and Let Us Sing, Bible passage retrieval, and exports to LaTeX for professional bulletin production.

---

## Header Bar

The header bar shows:
- **New / Open / Undo** buttons (left)
- **Window title** (centre, click to open service info popover)
- **Lectionary year tracker** — coloured dot + "Year A · Advent" showing today's RCL year and season. Hover for the full week name.
- **Document icon** — quick LaTeX export (Ctrl+E); right-click to change or unlink file
- **Print icon** — compile to PDF via xelatex (Ctrl+Shift+P)
- **Save** button
- **Hamburger menu**

---

## Service Info Popover

Click the window title to open. Contains:
- **Service title** — free text, appears in the LaTeX `\title{}`
- **Date picker** — drives the RCL readings, hymn suggestions, and the `\date{}` in the export

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

### Weekday services
Weekday dates default to the next Sunday's readings with a ← → stepper. Useful for Thursday chapels.

---

## Hymn Suggestions Strip

When a date is set, suggested hymns for the RCL week appear (VU, MV, LUS):
- **Left-click** a chip → opens inline Hymnary preview (if WebKit is installed) or browser
- **▶ button** → YouTube search
- **Right-click** a chip → injects `VU 16 — Mary, woman of the promise` into the **currently selected element's** Notes/Content

This means you can click "Opening Hymn" in your order list, then right-click a suggestion chip to fill it in — no new elements are created.

Suggestions are specific to the Proper (Propers 4–29) or season.

---

## Item Toolbar

Appears when any service element is selected:

| Field | Purpose |
|-------|---------|
| Leader: | Name/role — exports right-aligned italic in the `\section*` heading |
| Scripture: | Type any reference (e.g. `Ps 23`) and press Enter to open the Bible Viewer |
| Hymn #: | Type `VU 16` and press Enter to look up and inject the title |
| ✂ | Insert a snippet (Ctrl+Shift+I) |
| ℟ | Open the Responsive Reading builder (Ctrl+R) |

---

## Bible Viewer

Fetches World English Bible text. Click **Insert as LaTeX** to add a formatted `{scripture}` block to the selected element's Notes/Content.

The scripture block uses `\sverse{N}{text}` — verse number flush-left, continuation lines indented 2.4em, no inter-verse spacing.

---

## Hymn Lookup

Select a hymn-type element, type `VU 16` (or `MV 120`, `LUS 5`) in the **Hymn #** field and press Enter. The title is fetched from Hymnary.org and prepended to Notes/Content as `VU 16 — Mary, woman of the promise`. Results are cached.

---

## Snippets

**✂** button or Ctrl+Shift+I. Click any snippet to insert into Notes/Content.

Defaults: Land acknowledgement, Prayers of the People (full structure), Lord's Prayer (traditional and contemporary), Words of Assurance, Benediction, Words of Institution.

Manage in **Preferences → Snippets**.

---

## Responsive Reading Builder

**℟** button or Ctrl+R. Prefix lines `L:` (Leader) or `P:` (People); unprefixed lines alternate automatically. Inserts formatted LaTeX into Notes/Content.

---

## LaTeX Export

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
- **Export LaTeX…** — opens the file chooser (same as right-clicking the quick export button)
- **Export plain text…** — section headings and element names
- **Export CSV…** — Section, Element, Leader, Hymn ref, Notes preview (for musicians/AV)

---

## Templates

**Save order as template…** in the hamburger menu. Give it a name. Notes/Content is saved; date is not.

Multiple templates → chooser on New service. One template → applied silently.

Manage in **Preferences → Templates**.

---

## Git Integration

Hamburger menu → **Commit to git** (Ctrl+Shift+G). Stages and commits the `.liturgy` and linked `.tex` file with the message `Service: Title — Date`. The directory must be a git repo.

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
| Export LaTeX | Ctrl+E |
| Compile PDF | Ctrl+Shift+P |
| Add custom element | Ctrl+Shift+N |
| Add divider | Ctrl+D |
| Move item up | Ctrl+↑ |
| Move item down | Ctrl+↓ |
| Responsive reading | Ctrl+R |
| Insert snippet | Ctrl+Shift+I |
| Scripture search focus | Ctrl+Shift+F |
| Git commit | Ctrl+Shift+G |
| Preferences | Ctrl+, |
| Help | F1 |
