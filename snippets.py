"""
snippets.py — Named text snippet storage for Rubric.
Stored in ~/.local/share/rubric/rubric.db (snippets table).
"""

from pathlib import Path

try:
    from rubric_package.db import snippets_load as _db_load, snippets_save as _db_save, snippets_has_data
    _DB_OK = True
except ImportError:
    _DB_OK = False

# Fallback JSON path (legacy; used only if SQLite is unavailable)
_LEGACY_PATH = Path.home() / ".config/rubric/snippets.json"

def snippet_tags(snip: dict) -> list[str]:
    """Return the tags list for a snippet (empty list if absent)."""
    return snip.get("tags", [])


DEFAULT_SNIPPETS = [
    {
        "name": "Land acknowledgement (Mi'kmaq)",
        "tags": ["gathering", "indigenous"],
        "content": (
            "We acknowledge that we gather on the unceded ancestral territory "
            "of the Mi'kmaq people. We are grateful for their stewardship of "
            "this land and we commit ourselves to the ongoing work of "
            "reconciliation."
        ),
    },
    {
        "name": "Words of assurance",
        "content": (
            "Friends, believe the good news of the gospel: "
            "in Jesus Christ we are forgiven."
        ),
    },
    {
        "name": "Call to offering",
        "content": (
            "As we have received so freely, let us give freely. "
            "We bring our gifts as an act of worship and love."
        ),
    },
    {
        "name": "Prayers of the People",
        "content": r"""\textit{Preamble}

Friends,\\
Please sit comfortably and gently,\\
as we present ourselves to God in prayer:

\textit{Praise}

\textit{Lament}

\textit{Asks}

\textit{Intercession}

\medskip
\textit{Optional, if people ask for prayers:}

O Lord, Please give special attention,\\
as you look upon us with your infinite love, to:

\medskip
\hspace{2em}\rule{4cm}{0.4pt}

\hspace{2em}\rule{4cm}{0.4pt}

\hspace{2em}\rule{4cm}{0.4pt}

\medskip
And Continue:

\medskip
Let us now, in silence,\\
give our prayers,\\
for all those whom we wish to remember\\
for all those we wish God to touch:

\medskip
\textit{Silence}

\medskip
\textit{Inclusion}

Holy God,\\
As you look upon us with your infinite love,\\
please remember all we have forgotten to name,\\
our neighbours,\\
our enemies,\\
ourselves.""",
    },
    {
        "name": "Lord's Prayer (traditional poetic)",
        "content": r"""And now: we gathered,\\
We Body of Christ,\\
Let us join in prayer,\\
Saying the words Jesus taught us\\
so long ago\\
in the forms we love best:

\medskip
Our Father\\
Who art in Heaven\\
Hallowed be thy name\\
thy kingdom come,\\
thy will be done,\\
on earth as it is in heaven.

Give us this day our daily bread.

And forgive us our trespasses,\\
as we forgive those\\
who trespass against us.

And let us not fall into temptation\\
but deliver us from evil.

For thine is the kingdom,\\
and the power, and the glory,\\
for ever and ever.

Amen.""",
    },
    {
        "name": "Lord's Prayer (contemporary)",
        "content": (
            "Our Father in heaven, hallowed be your name, "
            "your kingdom come, your will be done, on earth as in heaven. "
            "Give us today our daily bread. "
            "Forgive us our sins as we forgive those who sin against us. "
            "Save us from the time of trial and deliver us from evil. "
            "For the kingdom, the power, and the glory are yours, "
            "now and for ever. Amen."
        ),
    },
    {
        "name": "Benediction",
        "content": r"""And may the grace of our Lord, Jesus Christ,\\
the love of God,\\
and the fellowship of the Holy Spirit\\
be with you all,\\
this day and always.""",
    },
    {
        "name": "Words of Institution",
        "content": (
            "On the night he was betrayed, Jesus took bread, "
            "and when he had given thanks, he broke it and said, "
            "\\textit{This is my body, which is for you; do this in remembrance of me.}\n\n"
            "In the same way, after supper he took the cup, saying, "
            "\\textit{This cup is the new covenant in my blood; "
            "do this, whenever you drink it, in remembrance of me.}\n\n"
            "For whenever you eat this bread and drink this cup, "
            "you proclaim the Lord's death until he comes."
        ),
    },
]


def load_snippets() -> list[dict]:
    if _DB_OK:
        if not snippets_has_data():
            # Seed defaults on a brand-new install (migration from JSON handled by db.migrate_from_json)
            _db_save(list(DEFAULT_SNIPPETS))
        return _db_load()

    # Legacy JSON fallback (no SQLite)
    import json
    if _LEGACY_PATH.exists():
        try:
            return json.loads(_LEGACY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return list(DEFAULT_SNIPPETS)


def save_snippets(snippets: list[dict]) -> None:
    if _DB_OK:
        _db_save(snippets)
        return

    # Legacy JSON fallback
    import json
    _LEGACY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEGACY_PATH.write_text(
        json.dumps(snippets, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
