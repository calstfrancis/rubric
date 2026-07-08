#!/usr/bin/env bash
# capture-screenshots.sh — capture a fresh screenshot of Rubric against demo data
#
# Launches the app from source under a throwaway $HOME (so it never touches
# Cal's real config/data or opens any real liturgy), inside an isolated Xvfb
# display forced via GDK_BACKEND=x11 (GTK4 otherwise prefers the real Wayland
# session and would render on the actual desktop). Waits for the window to
# render, screenshots just the window, and overwrites screenshots/rubric-main.png.
#
# Requires: Xvfb, ImageMagick (magick), python3-gi/gtk4/libadwaita (same deps
# as running Rubric normally).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DEMO_HOME=$(mktemp -d /tmp/rubric-demo-home.XXXXXX)
OUT="screenshots/rubric-main.png"

cleanup() {
  [[ -n "${APP_PID:-}" ]] && kill "$APP_PID" 2>/dev/null || true
  [[ -n "${XVFB_PID:-}" ]] && kill "$XVFB_PID" 2>/dev/null || true
  rm -rf "$DEMO_HOME"
}
trap cleanup EXIT

APP_VERSION=$(grep '^APP_VERSION' rubric.py | head -1 | sed 's/APP_VERSION = "\(.*\)"/\1/')

echo "==> Seeding demo config in $DEMO_HOME"
mkdir -p "$DEMO_HOME/.config/rubric" "$DEMO_HOME/.local/share/rubric"
cp screenshots/demo.liturgy "$DEMO_HOME/demo.liturgy"
cat > "$DEMO_HOME/.config/rubric/config.json" <<JSON
{
  "recent_files": ["$DEMO_HOME/demo.liturgy"],
  "first_launch_completed": true,
  "quickstart_dismissed": true,
  "last_seen_version": "$APP_VERSION",
  "simple_mode": true
}
JSON

# Isolated Xvfb display, well clear of any real display number in use.
DISPLAY_NUM=220
while [[ -e "/tmp/.X${DISPLAY_NUM}-lock" ]]; do
  DISPLAY_NUM=$((DISPLAY_NUM + 1))
done

echo "==> Starting isolated Xvfb on :$DISPLAY_NUM"
Xvfb ":$DISPLAY_NUM" -screen 0 1280x800x24 &
XVFB_PID=$!
sleep 2

echo "==> Launching Rubric against demo data inside the isolated display"
# GDK_BACKEND=x11 + unsetting WAYLAND_DISPLAY is required: GTK4 prefers Wayland
# by default, which would otherwise connect to the real desktop session and
# render there instead of into the isolated Xvfb display.
env -u WAYLAND_DISPLAY GDK_BACKEND=x11 HOME="$DEMO_HOME" DISPLAY=":$DISPLAY_NUM" python3 rubric.py &
APP_PID=$!

echo "==> Waiting for window to render"
sleep 10

echo "==> Capturing and cropping to the app window"
DISPLAY=":$DISPLAY_NUM" magick x:root -crop 1000x700+0+0 +repage "$OUT"

echo "Done. Wrote $OUT"
