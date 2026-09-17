#!/bin/sh
# Build a brief with the deterministic CLI, then show it the best way this
# harness allows: open the committed static renderer when a browser is available,
# otherwise print the Markdown. No network, no server. Display-only.
#
# Usage:
#   skills/brief/show-brief.sh --company <id>
#   skills/brief/show-brief.sh --portfolio
#   (any extra flags, e.g. --period 2026-06-30 or --records <path>, pass through)
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
RENDERER="$ROOT/renderer/dist/index.html"

# Build the brief. Capture the JSON envelope for the file paths.
RESULT=$(python3 "$ROOT/cli/run.py" brief "$@" --json) || {
  echo "$RESULT" >&2
  echo "brief: build failed" >&2
  exit 1
}

MD_PATH=$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["markdown_path"])')
JSON_PATH=$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["json_path"])')

echo "Brief written:"
echo "  blueprint: $JSON_PATH"
echo "  markdown:  $MD_PATH"

# Decide how to present it. A browser is "available" when a GUI opener exists and
# we are attached to a terminal (not a headless/CI run).
OPENER=""
if command -v open >/dev/null 2>&1; then
  OPENER="open"                      # macOS
elif command -v xdg-open >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  OPENER="xdg-open"                  # Linux with a display
fi

if [ -n "$OPENER" ] && [ -t 1 ] && [ -z "${IMPACTOS_BRIEF_NO_BROWSER:-}" ] && [ -f "$RENDERER" ]; then
  echo ""
  echo "Opening the renderer. Pick the blueprint file above in the file dialog."
  "$OPENER" "$RENDERER"
else
  echo ""
  echo "No browser available; showing the Markdown brief:"
  echo "----------------------------------------------------------------------"
  cat "$MD_PATH"
fi
