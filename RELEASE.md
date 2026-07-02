# Rubric v0.17.9 "Quiet Margin"

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

**Events display reworked** — the two-bar status bar layout (liturgical events row + separate justice bar) is replaced by a single compact `● Season` button. Click it to open a popover listing the previous and upcoming liturgical observances and justice/custom dates together, with an "Edit dates…" link. One bar, all the information.

**Preview compile mode moved** — the Auto / Save / Manual compile cycle button now lives in the preview panel header next to the ⟳ button, rather than in a second toolbar that only appeared when the preview was open.

**Visual polish throughout** — section element rows now have a 3 px left border in their section colour (replacing the small dot); section divider rows are full-width headers with a 6 px colour stripe. Mode buttons (SIMPLE, GOST, Compact…) show a tinted pill background when active. Word count and time labels appear as rounded metric chips. RCL reading chips pick up a subtle tint from the current liturgical season colour. The season gradient on the header bar is stronger and wider.

**Undo on element removal** — deleting an element shows a toast with an Undo button.

**Word count chip** — a live "N words · ~M min" pill in the status bar right, counting spoken words at 130 wpm.

**Duplicate element (Ctrl+Shift+D)** — duplicates the selected element or section divider and inserts the copy directly below.

**Planner Today button** — jumps the Service Planner calendar to this Sunday.

**Recently opened in Archive** — the Archive tab shows a "Recently opened" section at the top for quick re-access.

---

### Full changelog

See [CHANGELOG.md](CHANGELOG.md).
