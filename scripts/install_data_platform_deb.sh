#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$HOME/Data-Platform"
APP_DIR="$PROJECT_ROOT/application/data-platform-app"
BUNDLE_DIR="$APP_DIR/src-tauri/target/release/bundle/deb"
INSTALL_DIR="/tmp/data-platform-install"
SAFE_DEB="$INSTALL_DIR/data-platform_0.1.0_amd64.deb"

echo "Preparing clean Data Platform installer..."

mkdir -p "$INSTALL_DIR"

DEB_FILE="$(find "$BUNDLE_DIR" -maxdepth 1 -type f -name "*.deb" | head -n 1)"

if [ -z "$DEB_FILE" ]; then
  echo "ERROR: No .deb file found in $BUNDLE_DIR"
  exit 1
fi

cp "$DEB_FILE" "$SAFE_DEB"
chmod 644 "$SAFE_DEB"

echo "Installing:"
echo "$SAFE_DEB"

sudo apt install "$SAFE_DEB"

echo "Data Platform installed cleanly."
