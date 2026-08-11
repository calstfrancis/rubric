"""Shared notice/error dialog.

`Adw.MessageDialog`'s body text isn't selectable, so a raw error message
shown in one of these boxes could only ever be read on screen or
screenshotted — never copied into a bug report or a chat. `notice()` adds a
Copy button alongside OK so the message text can be pasted elsewhere.
"""

from __future__ import annotations

from gi.repository import Adw, Gdk


def notice(parent, heading: str, body: str) -> Adw.MessageDialog:
    """A plain acknowledgement, with a Copy button next to OK.

    Returns the dialog in case a caller needs to hold a reference (e.g. to
    call `.present()` after further setup), though the common case is just
    `notice(self, "Title", "message")`.
    """
    dlg = Adw.MessageDialog(transient_for=parent, heading=heading, body=body)
    dlg.add_response("copy", "Copy")
    dlg.add_response("ok", "OK")
    dlg.set_default_response("ok")
    dlg.set_close_response("ok")

    def on_response(_d, response):
        if response == "copy":
            display = Gdk.Display.get_default()
            if display is not None:
                display.get_clipboard().set(body)

    dlg.connect("response", on_response)
    dlg.present()
    return dlg
