#!/bin/sh
# Stop the Hermes in Chrome bridge and remove what install.sh put in place.
# The extension is removed separately, on chrome://extensions.
set -eu

TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/hermes-in-chrome"
LABEL="io.github.rezaulhreza.hermes-in-chrome"

case "$(uname -s)" in
  Darwin)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
    ;;
  Linux)
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now hermes-in-chrome.service 2>/dev/null || true
      rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/hermes-in-chrome.service"
      systemctl --user daemon-reload
    fi
    ;;
esac

rm -f "$TARGET/bridge.py"
rmdir "$TARGET" 2>/dev/null || true

echo "The bridge has been removed."
echo "To remove the extension, open chrome://extensions and choose Remove."
