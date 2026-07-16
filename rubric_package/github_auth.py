"""GitHub OAuth device-flow sign-in and repository creation.

Mirrors Zerkalo's src/github_auth.rs (device flow), adapted to urllib.request
to match Rubric's existing stdlib-only HTTP convention (see bible_api.py).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Client ID for Rubric's GitHub OAuth App (Device Flow enabled).
# Client IDs are not secret — safe to bake into the source.
CLIENT_ID = "Ov23lijSuf54S4GuakoP"

USER_AGENT = "Rubric (https://github.com/calstfrancis/rubric)"


class GithubAuthError(Exception):
    """Raised for any device-flow or GitHub API failure, with a user-facing message."""


class GithubAuthCancelled(GithubAuthError):
    """Raised when the caller signals cancellation via poll_for_access_token's cancel_event."""


def _request(url: str, data: dict[str, str] | None = None, token: str | None = None,
             method: str = "POST") -> Any:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None
    if data is not None:
        if method == "POST" and url.startswith("https://api.github.com/"):
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        msg = payload.get("message") or payload.get("error_description") or payload.get("error")
        raise GithubAuthError(msg or f"GitHub error: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise GithubAuthError(f"Network error: {e.reason}") from e


def request_device_code(client_id: str) -> dict[str, Any]:
    """Starts the device flow: returns user_code/verification_uri to display
    plus a device_code used to poll for approval."""
    return _request(
        "https://github.com/login/device/code",
        data={"client_id": client_id, "scope": "repo"},
    )


def poll_for_access_token(client_id: str, device: dict[str, Any],
                           cancel_event: threading.Event | None = None) -> str:
    """Blocks, polling GitHub until the user approves (or denies/expires) the
    device code. Intended to run on a background thread.

    If cancel_event is given and gets set, stops polling and raises
    GithubAuthCancelled instead of waiting out the remaining interval."""
    interval = max(int(device.get("interval", 5)), 1)
    deadline = time.monotonic() + int(device.get("expires_in", 900))

    while True:
        if cancel_event is not None:
            if cancel_event.wait(interval):
                raise GithubAuthCancelled("Sign-in was cancelled.")
        else:
            time.sleep(interval)
        if time.monotonic() > deadline:
            raise GithubAuthError("The sign-in code expired before it was approved. Try again.")

        resp = _request(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "device_code": device["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )

        token = resp.get("access_token")
        if token:
            return token

        error = resp.get("error")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval += 5
            continue
        elif error == "expired_token":
            raise GithubAuthError("The sign-in code expired before it was approved. Try again.")
        elif error == "access_denied":
            raise GithubAuthError("Sign-in was cancelled or denied.")
        else:
            raise GithubAuthError(f"GitHub error: {error or 'unknown response'}")


def fetch_username(token: str) -> str:
    """Returns the login name of the authenticated user."""
    resp = _request("https://api.github.com/user", token=token, method="GET")
    return resp["login"]


def create_repo(token: str, name: str, private: bool = True) -> str:
    """Creates a new repository under the authenticated user's account and
    returns its HTTPS clone URL."""
    resp = _request(
        "https://api.github.com/user/repos",
        data={"name": name, "private": private},
        token=token,
    )
    return resp["clone_url"]
