"""github_signin — modal "Sign in with GitHub" dialog driving the OAuth device flow."""

from __future__ import annotations

import threading
from typing import Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from rubric_package import github_auth, secret_store


def present(parent: Gtk.Window, on_connected: Callable[[str, str], None]) -> None:
    """Shows a modal sign-in dialog that requests a device code, displays it
    alongside a link to open the verification page, polls for approval,
    stores the resulting token in the system keyring, and calls
    on_connected(token, username) once signed in."""

    dialog = Adw.Window(transient_for=parent, modal=True,
                        default_width=420, default_height=280, resizable=False)
    dialog.set_title("Sign in with GitHub")

    header = Adw.HeaderBar()
    header.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label="Cancel")
    cancel_btn.add_css_class("flat")
    header.pack_start(cancel_btn)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_margin_start(16); box.set_margin_end(16)
    box.set_margin_top(16); box.set_margin_bottom(16)

    status_lbl = Gtk.Label(label="Requesting a sign-in code from GitHub…")
    status_lbl.set_wrap(True); status_lbl.set_xalign(0.0)
    box.append(status_lbl)

    code_lbl = Gtk.Label()
    code_lbl.add_css_class("title-1")
    code_lbl.set_selectable(True)
    code_lbl.set_margin_top(12)
    code_lbl.set_visible(False)
    box.append(code_lbl)

    open_link = Gtk.LinkButton(uri="https://github.com/login/device", label="Open github.com/login/device ↗")
    open_link.set_halign(Gtk.Align.CENTER)
    open_link.set_margin_top(8)
    open_link.set_visible(False)
    box.append(open_link)

    spinner = Gtk.Spinner()
    spinner.set_spinning(True)
    spinner.set_margin_top(16)
    spinner.set_halign(Gtk.Align.CENTER)
    box.append(spinner)

    tv = Adw.ToolbarView()
    tv.add_top_bar(header)
    tv.set_content(box)
    dialog.set_content(tv)

    cancel_btn.connect("clicked", lambda _b: dialog.close())

    def _on_code(device: dict) -> bool:
        status_lbl.set_label("Enter this code at github.com to connect your account:")
        code_lbl.set_label(device["user_code"])
        code_lbl.set_visible(True)
        open_link.set_uri(device["verification_uri"])
        open_link.set_visible(True)
        return False

    def _on_failed(message: str) -> bool:
        status_lbl.set_label(f"Sign-in failed: {message}")
        spinner.set_spinning(False)
        return False

    def _on_success(token: str, username: str) -> bool:
        try:
            secret_store.save_github_token(token)
        except Exception as e:
            status_lbl.set_label(f"Signed in, but couldn't store the token: {e}")
            spinner.set_spinning(False)
            return False
        dialog.close()
        on_connected(token, username)
        return False

    def run() -> None:
        try:
            device = github_auth.request_device_code(github_auth.CLIENT_ID)
        except github_auth.GithubAuthError as e:
            GLib.idle_add(_on_failed, str(e))
            return
        GLib.idle_add(_on_code, device)

        try:
            token = github_auth.poll_for_access_token(github_auth.CLIENT_ID, device)
            username = github_auth.fetch_username(token)
        except github_auth.GithubAuthError as e:
            GLib.idle_add(_on_failed, str(e))
            return
        GLib.idle_add(_on_success, token, username)

    threading.Thread(target=run, daemon=True).start()
    dialog.present()
