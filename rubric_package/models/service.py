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
    ) -> None:
        self.name = name
        self.section = section
        self.note = note
        self.leader = leader
        self.show_in_bulletin = show_in_bulletin  # whether element appears in bulletin
        self.bulletin_note = bulletin_note       # congregation-facing text (overrides note)
        self.prep_note = prep_note               # private prep/sermon notes — never exported
        self.duration = duration                 # estimated duration in minutes (0 = unset)

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
        }
        if self.prep_note:
            d["prep_note"] = self.prep_note
        if self.duration:
            d["duration"] = self.duration
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ServiceItem:
        """Deserialize from dictionary."""
        return cls(
            d["name"],
            d.get("section", ""),
            d.get("note", ""),
            d.get("leader", ""),
            d.get("show_in_bulletin", True),
            d.get("bulletin_note", ""),
            d.get("prep_note", ""),
            d.get("duration", 0),
        )

    def __repr__(self) -> str:
        return (
            f"ServiceItem(name={self.name!r}, section={self.section!r}, "
            f"leader={self.leader!r})"
        )


def entry_from_dict(d: dict) -> SectionDivider | ServiceItem:
    """Deserialize a service entry from dictionary."""
    return SectionDivider.from_dict(d) if d.get("type") == "divider" else ServiceItem.from_dict(d)
