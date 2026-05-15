#!/usr/bin/env bash
# Rubric — install script
# Installs the app, icons, and .desktop entry to ~/.local
# Run from the directory containing this script.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/rubric"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

# ── Dependency check ──────────────────────────────────────────────────────────
echo "==> Checking dependencies…"
python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
print('  GTK4 + libadwaita: OK')
" 2>/dev/null || {
    echo ""
    echo "  Dependencies not found. Install with:"
    echo "    sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0"
    echo ""
    exit 1
}

# ── App files ─────────────────────────────────────────────────────────────────
echo "==> Installing app to $APP_DIR"
mkdir -p "$APP_DIR"
cp "$SCRIPT_DIR/rubric.py"  "$APP_DIR/"
cp "$SCRIPT_DIR/rcl_data.py"         "$APP_DIR/"

# Optional modules — copy if present
for f in hymn_lookup.py hymn_suggestions.py bible_api.py snippets.py; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$APP_DIR/"
done

# Data files (hymn suggestions JSON, etc.)
if [ -d "$SCRIPT_DIR/data" ]; then
    mkdir -p "$APP_DIR/data"
    cp "$SCRIPT_DIR/data/"* "$APP_DIR/data/"
fi

# Documentation
for f in HELP.md FAQ.md CHANGELOG.md; do
    [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$APP_DIR/"
done

# ── Launcher ──────────────────────────────────────────────────────────────────
echo "==> Creating launcher at $BIN_DIR/rubric"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/rubric" << 'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/rubric/rubric.py" "$@"
EOF
chmod +x "$BIN_DIR/rubric"

# ── Icons ─────────────────────────────────────────────────────────────────────
echo "==> Installing icons"

mkdir -p "$ICON_BASE/scalable/apps"
mkdir -p "$ICON_BASE/symbolic/apps"

_ICON_SVG='<svg viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="plate" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#9B57C5"/>
      <stop offset="100%" stop-color="#5C2D91"/>
    </linearGradient>
    <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#ffffff" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.0"/>
    </linearGradient>
    <radialGradient id="flame-out" cx="50%" cy="80%" r="55%">
      <stop offset="0%"   stop-color="#FFE566"/>
      <stop offset="60%"  stop-color="#FFA830"/>
      <stop offset="100%" stop-color="#E05C00" stop-opacity="0.7"/>
    </radialGradient>
    <radialGradient id="flame-in" cx="50%" cy="75%" r="50%">
      <stop offset="0%"   stop-color="#FFFBE0"/>
      <stop offset="100%" stop-color="#FFE04A" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="page-l" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="#F4EEFF"/>
      <stop offset="100%" stop-color="#E8E0F8"/>
    </linearGradient>
    <linearGradient id="page-r" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="#E8E0F8"/>
      <stop offset="100%" stop-color="#DDD4F2"/>
    </linearGradient>
  </defs>
  <rect x="6" y="7" width="116" height="116" rx="24" fill="#000000" opacity="0.22"/>
  <rect x="8" y="8" width="112" height="112" rx="22" fill="url(#plate)"/>
  <rect x="8" y="8" width="112" height="56" rx="22" fill="url(#rim)"/>
  <path d="M 18 54 C 18 50, 42 46, 61 46 L 61 94 C 42 94, 18 96, 18 91 Z" fill="url(#page-l)"/>
  <path d="M 110 54 C 110 50, 86 46, 67 46 L 67 94 C 86 94, 110 96, 110 91 Z" fill="url(#page-r)"/>
  <rect x="59" y="46" width="3" height="48" rx="1" fill="#4A2080" opacity="0.20"/>
  <rect x="66" y="46" width="3" height="48" rx="1" fill="#4A2080" opacity="0.10"/>
  <path d="M 18 91 C 18 95, 42 97, 64 97 C 86 97, 110 95, 110 91 L 110 94 C 110 98, 86 100, 64 100 C 42 100, 18 98, 18 94 Z" fill="#C8B8E8" opacity="0.55"/>
  <line x1="26" y1="56" x2="57" y2="56" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="26" y1="63" x2="55" y2="63" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="26" y1="70" x2="57" y2="70" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="26" y1="77" x2="53" y2="77" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="26" y1="84" x2="56" y2="84" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="71" y1="56" x2="102" y2="56" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="71" y1="63" x2="100" y2="63" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="71" y1="70" x2="102" y2="70" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="71" y1="77" x2="98" y2="77" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="71" y1="84" x2="101" y2="84" stroke="#A088CC" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <rect x="59.5" y="32" width="9" height="16" rx="2.5" fill="#F8F2E2" stroke="#E0D4B8" stroke-width="0.8"/>
  <path d="M 59.5 36 Q 57 37 57.5 39 Q 58 40 59.5 40 Z" fill="#F0E8D0" opacity="0.7"/>
  <path d="M 64 32 Q 64.5 29 64 27" stroke="#3D2010" stroke-width="1.4" stroke-linecap="round" fill="none"/>
  <path d="M 64 13 C 59 18, 54 22, 55 28 C 56 33, 60 34, 64 34 C 68 34, 72 33, 73 28 C 74 22, 69 18, 64 13 Z" fill="url(#flame-out)"/>
  <path d="M 64 17 C 61.5 21, 59 24, 59.5 28 C 60 31, 62.5 32, 64 32 C 65.5 32, 68 31, 68.5 28 C 69 24, 66.5 21, 64 17 Z" fill="url(#flame-in)"/>
  <ellipse cx="64" cy="19" rx="2.5" ry="3.5" fill="white" opacity="0.55"/>
</svg>'

_SYM_SVG='<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
  <path d="M 8 0.75 C 6.8 2.2, 5.5 3.2, 5.75 4.7 C 6 6, 7 6.5, 8 6.5 C 9 6.5, 10 6, 10.25 4.7 C 10.5 3.2, 9.2 2.2, 8 0.75 Z" fill="currentColor"/>
  <rect x="7" y="6.25" width="2" height="2.75" rx="0.5" fill="currentColor" opacity="0.6"/>
  <path d="M 1 6 C 1 5.5, 4 5, 6.8 5 L 6.8 14.5 C 4 14.5, 1 14.2, 1 13.5 Z" fill="currentColor" opacity="0.9"/>
  <path d="M 15 6 C 15 5.5, 12 5, 9.2 5 L 9.2 14.5 C 12 14.5, 15 14.2, 15 13.5 Z" fill="currentColor" opacity="0.7"/>
  <rect x="6.7" y="5" width="2.6" height="9.5" rx="0.3" fill="currentColor" opacity="0.25"/>
</svg>'

# Write full-colour icon under BOTH names so GNOME Shell panel finds it
# by app-id AND the short name used by the .desktop Icon= field
echo "$_ICON_SVG" > "$ICON_BASE/scalable/apps/rubric.svg"
echo "$_ICON_SVG" > "$ICON_BASE/scalable/apps/io.github.calstfrancis.rubric.svg"

# Symbolic icon likewise
echo "$_SYM_SVG" > "$ICON_BASE/symbolic/apps/rubric-symbolic.svg"
echo "$_SYM_SVG" > "$ICON_BASE/symbolic/apps/io.github.calstfrancis.rubric-symbolic.svg"

# Update the icon cache so GTK finds the icons immediately.
# Try gtk4-update-icon-cache first (GNOME 42+), fall back to older tool.
if command -v gtk4-update-icon-cache &>/dev/null; then
    gtk4-update-icon-cache -f -t "$ICON_BASE"
elif command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_BASE"
else
    echo "  (gtk-update-icon-cache not found — you may need to log out and back in)"
fi

# ── Desktop entry ─────────────────────────────────────────────────────────────
echo "==> Writing .desktop entry"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/rubric.desktop" << EOF
[Desktop Entry]
Name=Rubric
GenericName=Worship Service Planner
Comment=Plan worship service orders with RCL readings
Exec=$BIN_DIR/rubric %f
Icon=io.github.calstfrancis.rubric
Terminal=false
Type=Application
Categories=Office;Education;
Keywords=worship;liturgy;service;church;UCC;lectionary;RCL;
StartupNotify=true
StartupWMClass=rubric
MimeType=application/x-liturgy;
EOF

# Register MIME type so .liturgy files open in the app
mkdir -p "$HOME/.local/share/mime/packages"
cat > "$HOME/.local/share/mime/packages/rubric.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-liturgy">
    <comment>Rubric service file</comment>
    <glob pattern="*.liturgy"/>
  </mime-type>
</mime-info>
EOF

if command -v update-mime-database &>/dev/null; then
    update-mime-database "$HOME/.local/share/mime" 2>/dev/null || true
fi

# Notify the desktop environment about the new .desktop entry
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "Done! Rubric is installed."
echo ""
echo "  Run from terminal:     rubric"
echo "  Or search in KRunner:  Rubric"
echo ""
echo "  .liturgy files will open in the app automatically."
echo ""
echo "  To uninstall:"
echo "    rm -rf $APP_DIR"
echo "    rm $BIN_DIR/rubric"
echo "    rm $DESKTOP_DIR/rubric.desktop"
echo "    rm $ICON_BASE/scalable/apps/rubric.svg"
echo "    rm $ICON_BASE/symbolic/apps/rubric-symbolic.svg"
