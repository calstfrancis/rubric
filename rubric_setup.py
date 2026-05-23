"""
rubric_setup — desktop integration installer for Rubric.

Run after installing via pipx or pip:

    rubric-desktop-install

Installs:
  - App icon to ~/.local/share/icons/hicolor/
  - .desktop entry to ~/.local/share/applications/
  - MIME type (*.liturgy) to ~/.local/share/mime/

Safe to re-run; updates existing entries.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def _find_icon(name: str) -> Path | None:
    try:
        import rubric_package
        p = Path(rubric_package.__file__).parent / "data" / name
        if p.exists():
            return p
    except ImportError:
        pass
    # fallback: same directory as this script (git clone path)
    p = Path(__file__).parent / name
    return p if p.exists() else None


def main() -> None:
    icon_base  = Path.home() / ".local/share/icons/hicolor"
    apps_dir   = Path.home() / ".local/share/applications"
    mime_dir   = Path.home() / ".local/share/mime/packages"

    # ── Resolve rubric binary ─────────────────────────────────────────────────
    rubric_bin = shutil.which("rubric")
    if not rubric_bin:
        local_bin = Path.home() / ".local/bin/rubric"
        rubric_bin = str(local_bin) if local_bin.exists() else "rubric"

    # ── Icons ─────────────────────────────────────────────────────────────────
    scalable = icon_base / "scalable/apps"
    symbolic = icon_base / "symbolic/apps"
    scalable.mkdir(parents=True, exist_ok=True)
    symbolic.mkdir(parents=True, exist_ok=True)

    full_icon = _find_icon("rubric.svg")
    sym_icon  = _find_icon("rubric-symbolic.svg")

    if full_icon:
        shutil.copy2(full_icon, scalable / "rubric.svg")
        shutil.copy2(full_icon, scalable / "io.github.calstfrancis.rubric.svg")
        print(f"  icon → {scalable}/rubric.svg")
    else:
        print("  WARNING: rubric.svg not found — icon not installed", file=sys.stderr)

    if sym_icon:
        shutil.copy2(sym_icon, symbolic / "rubric-symbolic.svg")
        shutil.copy2(sym_icon, symbolic / "io.github.calstfrancis.rubric-symbolic.svg")
        print(f"  icon → {symbolic}/rubric-symbolic.svg")

    for cmd in ("gtk4-update-icon-cache", "gtk-update-icon-cache"):
        if shutil.which(cmd):
            subprocess.run([cmd, "-f", "-t", str(icon_base)],
                           capture_output=True)
            break

    # ── .desktop entry ────────────────────────────────────────────────────────
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop = apps_dir / "rubric.desktop"
    desktop.write_text(
        "[Desktop Entry]\n"
        "Name=Rubric\n"
        "GenericName=Worship Service Planner\n"
        "Comment=Plan worship service orders with RCL readings\n"
        f"Exec={rubric_bin} %f\n"
        "Icon=io.github.calstfrancis.rubric\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Office;Education;\n"
        "Keywords=worship;liturgy;service;church;UCC;lectionary;RCL;\n"
        "StartupNotify=true\n"
        "StartupWMClass=rubric\n"
        "MimeType=application/x-liturgy;\n",
        encoding="utf-8",
    )
    print(f"  desktop → {desktop}")

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(apps_dir)],
                       capture_output=True)

    # ── MIME type ─────────────────────────────────────────────────────────────
    mime_dir.mkdir(parents=True, exist_ok=True)
    mime_xml = mime_dir / "rubric.xml"
    mime_xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
        '  <mime-type type="application/x-liturgy">\n'
        '    <comment>Rubric service file</comment>\n'
        '    <glob pattern="*.liturgy"/>\n'
        '  </mime-type>\n'
        '</mime-info>\n',
        encoding="utf-8",
    )
    print(f"  mime  → {mime_xml}")

    if shutil.which("update-mime-database"):
        subprocess.run(["update-mime-database",
                        str(Path.home() / ".local/share/mime")],
                       capture_output=True)

    print()
    print("Desktop integration installed.")
    print("Rubric will now appear in your application launcher.")
    print("Log out and back in if the icon doesn't appear immediately.")


if __name__ == "__main__":
    main()
