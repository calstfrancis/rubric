"""Service data models for Rubric."""

from __future__ import annotations

from rubric_package.models import content as _content


class SectionDivider:
    """A section divider in the service order."""

    is_divider = True

    def __init__(self, title: str = "New section") -> None:
        self.title = title

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {"type": "divider", "title": self.title}

    @classmethod
    def from_dict(cls, d: dict) -> SectionDivider:
        """Deserialize from dictionary."""
        return cls(d.get("title", "Section"))

    def __repr__(self) -> str:
        return f"SectionDivider(title={self.title!r})"


class ServiceItem:
    """A service item (element) in the service order."""

    is_divider = False

    def __init__(
        self,
        name: str,
        section: str,
        note: str = "",
        leader: str = "",
        show_in_bulletin: bool = True,
        bulletin_note: str = "",
        prep_note: str = "",
        duration: int = 0,
        content: list | None = None,
        content_mode: str = "rich",
        rubric_note: str = "",
        icon: str = "",
        bulletin_heading_only: bool = False,
        bulletin_summary: str = "",
    ) -> None:
        self.name = name
        self.section = section
        self.note = note
        self.leader = leader
        self.show_in_bulletin = show_in_bulletin
        self.bulletin_note = bulletin_note
        self.prep_note = prep_note
        self.duration = duration
        # The document itself — a list of blocks. See models/content.py. Typst
        # is an output format now and never appears in this field.
        self.content = _content.normalise(content)
        # "rich" or "typst"; not persisted (always opens in rich mode)
        self.content_mode = content_mode
        # Leader-only instructions (red italic, manuscript only)
        self.rubric_note = rubric_note
        # Optional user-assigned symbolic icon name
        self.icon = icon
        # Bulletin appears as heading only (no body text in bulletin)
        self.bulletin_heading_only = bulletin_heading_only
        # Short line shown in the bulletin instead of the full content
        self.bulletin_summary = bulletin_summary

    # ── content accessors ─────────────────────────────────────────────────────

    @property
    def content_typst(self) -> str:
        """The content rendered as Typst, for export and preview.

        Read-only and derived: assigning Typst to an element is what the old
        model allowed and what let markup leak back into the editor. Use
        :meth:`set_plain_text`, :meth:`append_text` or :meth:`prepend_text`.
        """
        return _content.blocks_to_typst(self.content)

    @property
    def content_plain(self) -> str:
        """The content as readable text, for word counts and previews."""
        return _content.blocks_to_plain(self.content)

    def set_plain_text(self, text: str) -> None:
        self.content = _content.plain_to_blocks(text)

    def append_text(self, text: str) -> None:
        self.content = _content.concat(self.content, _content.plain_to_blocks(text))

    def prepend_text(self, text: str) -> None:
        self.content = _content.concat(_content.plain_to_blocks(text), self.content)

    def has_content(self) -> bool:
        return not _content.is_empty(self.content)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        d = {
            "type": "item",
            "name": self.name,
            "section": self.section,
            "note": self.note,
            "leader": self.leader,
            "show_in_bulletin": self.show_in_bulletin,
            "bulletin_note": self.bulletin_note,
            "content": self.content,
        }
        if self.prep_note:
            d["prep_note"] = self.prep_note
        if self.duration:
            d["duration"] = self.duration
        if self.rubric_note:
            d["rubric_note"] = self.rubric_note
        if self.icon:
            d["icon"] = self.icon
        if self.bulletin_heading_only:
            d["bulletin_heading_only"] = True
        if self.bulletin_summary:
            d["bulletin_summary"] = self.bulletin_summary
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ServiceItem:
        """Deserialize from dictionary."""
        note         = d.get("note", "")
        bulletin_note = d.get("bulletin_note", "")
        prep_note    = d.get("prep_note", "")
        blocks = d.get("content")

        # Migration. Services written before the block model stored Typst in
        # "content_typst"; ones older still had only note/bulletin_note/prep_note.
        # Both are parsed into blocks on load and written back in the new format,
        # so a service is migrated the first time it is opened and saved.
        content_typst = "" if blocks is not None else d.get("content_typst", "")

        if blocks is None and not content_typst:
            import re as _re
            base = bulletin_note or note
            # Old LaTeX content (\command{...}) must be stripped to plain text —
            # embedding it verbatim in Typst markup breaks compilation.
            if base and _re.search(r'\\[a-zA-Z]', base):
                from rubric_package.utils.typst import strip_typst_plain
                base = strip_typst_plain(base)
            if prep_note:
                content_typst = (f"{base}\n" if base else "") + f"#leader-note[{prep_note}]"
            else:
                content_typst = base

        if blocks is None:
            blocks = _content.typst_to_blocks(content_typst)

        return cls(
            d.get("name", ""),
            d.get("section", ""),
            note,
            d.get("leader", ""),
            d.get("show_in_bulletin", True),
            bulletin_note,
            prep_note,
            d.get("duration", 0),
            blocks,
            rubric_note=d.get("rubric_note", ""),
            icon=d.get("icon", ""),
            bulletin_heading_only=d.get("bulletin_heading_only", False),
            bulletin_summary=d.get("bulletin_summary", ""),
        )

    def __repr__(self) -> str:
        return (
            f"ServiceItem(name={self.name!r}, section={self.section!r}, "
            f"leader={self.leader!r})"
        )


def entry_from_dict(d: dict) -> SectionDivider | ServiceItem:
    """Deserialize a service entry from dictionary."""
    return SectionDivider.from_dict(d) if d.get("type") == "divider" else ServiceItem.from_dict(d)
