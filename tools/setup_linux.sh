#!/usr/bin/env bash
# Install the FlexForge Linux toolchain: pwsh, Blender 4.2.3 + 5.2.0, Godot 4.7.2.
# Idempotent; requires sudo. Usage: bash tools/setup_linux.sh
set -euo pipefail
UA="Mozilla/5.0"

if ! command -v pwsh >/dev/null; then
  . /etc/os-release
  curl -fsSL -o /tmp/pmc.deb "https://packages.microsoft.com/config/${ID}/${VERSION_ID}/packages-microsoft-prod.deb"
  sudo dpkg -i /tmp/pmc.deb && rm -f /tmp/pmc.deb
  sudo apt-get update -qq && sudo apt-get install -y -qq powershell
fi

for v in 4.2.3 5.2.0; do
  d="/opt/blender/$v"
  if [ ! -x "$d/blender" ]; then
    sudo mkdir -p "$d"
    curl -fL -A "$UA" "https://download.blender.org/release/Blender${v%.*}/blender-$v-linux-x64.tar.xz" \
      | sudo tar -xJ -C "$d" --strip-components=1
  fi
done

if [ ! -x /opt/godot/godot ]; then
  sudo mkdir -p /opt/godot
  curl -fL -o /tmp/godot.zip https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip
  sudo unzip -o -q /tmp/godot.zip -d /opt/godot && rm -f /tmp/godot.zip
  sudo ln -sf /opt/godot/Godot_v4.7.2-stable_linux.x86_64 /opt/godot/godot
fi

pwsh -v; /opt/blender/4.2.3/blender -v | head -1; /opt/blender/5.2.0/blender -v | head -1
/opt/godot/godot --headless --version
echo "Gates: FLEXFORGE_BLENDER=/opt/blender/5.2.0/blender pwsh -NoProfile -File tools/scripts/run_gates.ps1"
