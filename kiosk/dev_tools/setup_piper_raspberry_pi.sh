#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
piper_root="$root/kiosk/models/piper"
bin_path="$piper_root/bin"
voice_path="$piper_root/voices"

voice_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx?download=true"
voice_config_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json?download=true"

mkdir -p "$bin_path" "$voice_path"

if ! command -v piper >/dev/null 2>&1 && [ ! -x "$bin_path/piper" ]; then
  cat >&2 <<EOF
Piper binary was not found.

Install a Raspberry Pi/Linux Piper binary, then either:
  - put it on PATH as: piper
  - or copy it to: $bin_path/piper

After installing the binary, run this script again to download the Amy voice.
EOF
  exit 1
fi

if [ ! -f "$voice_path/en_US-amy-medium.onnx" ]; then
  echo "Downloading Amy medium voice..."
  curl -L "$voice_url" -o "$voice_path/en_US-amy-medium.onnx"
fi

if [ ! -f "$voice_path/en_US-amy-medium.onnx.json" ]; then
  echo "Downloading Amy medium voice config..."
  curl -L "$voice_config_url" -o "$voice_path/en_US-amy-medium.onnx.json"
fi

echo "Piper is ready:"
if [ -x "$bin_path/piper" ]; then
  echo "  kiosk/models/piper/bin/piper"
else
  echo "  $(command -v piper)"
fi
echo "  kiosk/models/piper/voices/en_US-amy-medium.onnx"
