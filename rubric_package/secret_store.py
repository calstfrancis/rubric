"""GitHub token storage via the system keyring (libsecret)."""

from __future__ import annotations

import gi
gi.require_version("Secret", "1")
from gi.repository import Secret

_SCHEMA = Secret.Schema.new(
    "io.github.calstfrancis.rubric",
    Secret.SchemaFlags.NONE,
    {"account": Secret.SchemaAttributeType.STRING},
)
_ATTRIBUTES = {"account": "github_token"}


def save_github_token(token: str) -> None:
    Secret.password_store_sync(
        _SCHEMA, _ATTRIBUTES, Secret.COLLECTION_DEFAULT,
        "Rubric GitHub token", token, None,
    )


def load_github_token() -> str | None:
    return Secret.password_lookup_sync(_SCHEMA, _ATTRIBUTES, None)


def delete_github_token() -> None:
    Secret.password_clear_sync(_SCHEMA, _ATTRIBUTES, None)
