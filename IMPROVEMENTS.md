# Rubric — Improvement Suggestions

Prioritised by value to a working minister using this weekly, not by technical interest.

---

1. **Print bulletin directly from the app without a file-chooser step.**
   Right now "Export Bulletin" asks where to save the .tex, then compiles. Add a "Print Bulletin" button that writes to a temp directory and compiles silently — the minister just gets a PDF to send to the copier, no file management required.

2. **Bulletin preview before export.**
   A read-only rendered preview (even just formatted text in a dialog) lets the minister catch "Show in Bulletin" mistakes before printing 150 copies.

3. **Reusable bulletin templates / saved church info.**
   The church name, address, staff list, and mission statement never change week to week. These already live in preferences, but there is no quick-copy or "duplicate last week's bulletin" path. Saving the previous week's bulletin config as a starting point (separate from the service template) would save several minutes every week.

4. **Expiry-date UX for announcements.**
   Right now expiry is typed as `YYYY-MM-DD`. A calendar picker (the app already has `Gtk.Calendar` wired up) would be faster and eliminate format errors that silently keep expired announcements in the bulletin.

5. **"Copy to bulletin note" button per element.**
   When a scripture reading has detailed leader notes that should not appear in the pew bulletin, the minister must retype a shorter version in the "Bulletin note" field. A one-click "Copy first line only" or "Trim to bulletin" helper would prevent that extra step.

6. **Surface `print_mode`, `include_announcements`, and `include_scripture` as preferences.**
   These three config keys have no UI and silently stay `True`/`booklet` forever. Adding toggles to the Bulletin preferences tab would let the minister set "digital only" for a congregation that has moved away from printed bulletins, and opt out of printing full scripture passages in the pew copy.

7. **Date-stamped PDF filenames by default.**
   The suggested bulletin filename uses `church_name + date + suffix`. The leader-copy PDF uses the linked `.tex` filename, which is often just `service.pdf`. A consistent naming convention (`2024-12-01_service.pdf`, `2024-12-01_bulletin_print.pdf`) would make the weekly folder self-organising without any manual renaming.

8. **Per-reading "include in bulletin" toggle on the RCL readings card.**
   The `include_scripture` config key exists but is never applied to individual readings. Many ministers want the Psalm printed in full for congregational use but not the epistle. A per-reading toggle on the readings card would make the bulletin immediately useful for pew-use scripture following.

9. **Hymn number visible in the order-list row subtitle.**
   After looking up `VU 16 — O Come, O Come, Emmanuel`, the note preview shows "VU 16 — O Come, O Come…" but the row title remains just "Opening Hymn". Showing the hymn reference as part of the title or as a badge (`Opening Hymn · VU 16`) would let the minister scan the full order at a glance without selecting each element.

10. **One-click "send to music director" export.**
    The existing CSV export includes all columns including full LaTeX notes. A simpler export — element name, hymn number, leader, nothing else — formatted for a phone screen, would be something a minister could forward directly from the app without needing to open a spreadsheet first.
