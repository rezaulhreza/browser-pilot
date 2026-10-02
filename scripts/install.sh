#!/bin/sh
# Install the Browser Yolo Agent bridge and set it to start when you log in.
# macOS uses a launchd agent, Linux a systemd user service. Safe to run again to update.
set -eu

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/browser-yolo-agent"
PORT="${BROWSER_YOLO_AGENT_PORT:-8790}"
LABEL="io.github.rezaulhreza.browser-yolo-agent"

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "Python 3 was not found. Install it, then run this script again." >&2
  exit 1
fi

mkdir -p "$TARGET"
cp "$HERE/bridge/bridge.py" "$TARGET/bridge.py"

case "$(uname -s)" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
    cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$TARGET/bridge.py</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/browser-yolo-agent.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/browser-yolo-agent.log</string>
</dict>
</plist>
PLIST
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "The bridge is running and will start when you log in."
    echo "Log file  $HOME/Library/Logs/browser-yolo-agent.log"
    ;;
  Linux)
    if ! command -v systemctl >/dev/null 2>&1; then
      echo "systemd was not found. Start the bridge yourself with"
      echo "  $PYTHON $TARGET/bridge.py --port $PORT"
      exit 0
    fi
    UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT_DIR/browser-yolo-agent.service" <<UNIT
[Unit]
Description=Browser Yolo Agent bridge

[Service]
ExecStart=$PYTHON $TARGET/bridge.py --port $PORT
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable --now browser-yolo-agent.service
    echo "The bridge is running and will start when you log in."
    echo "Logs  journalctl --user -u browser-yolo-agent"
    ;;
  *)
    echo "This script supports macOS and Linux. Start the bridge yourself with"
    echo "  $PYTHON $TARGET/bridge.py --port $PORT"
    exit 0
    ;;
esac

echo
echo "Next"
echo "  1. In Chrome, open chrome://extensions, switch on Developer mode,"
echo "     choose Load unpacked and pick  $HERE/extension"
echo "  2. Point your agent at  http://127.0.0.1:$PORT/mcp"
