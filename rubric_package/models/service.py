"""Service data models for Rubric."""

from __future__ import annotations


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
        content_typst: str = "",
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
        # Unified content field (Phase 2).  Populated from old fields on load.
        self.content_typst = content_typst
        # "rich" or "typst"; not persisted (always opens in rich mode)
        self.content_mode = content_mode
        # Leader-only instructions (red italic, manuscript only)
        self.rubric_note = rubric_note
        # Optional user-assigned symbolic icon name
        self.icon = icon
        # Bulletin appears as heading only (no body text in bulletin)
        self.bulletin_heading_only = bulletin_heading_only
        # Short line shown in the bulletin instead of full content_typst
        self.bulletin_summary = bulletin_summary

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
            "content_typst": self.content_typst,
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
        content_typst = d.get("content_typst", "")

        # Migrate: build content_typst from old fields if the file pre-dates Phase 2
        if not content_typst:
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

        return cls(
            d.get("name", ""),
            d.get("section", ""),
            note,
            d.get("leader", ""),
            d.get("show_in_bulletin", True),
            bulletin_note,
            prep_note,
            d.get("duration", 0),
            content_typst,
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
