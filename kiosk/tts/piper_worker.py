"""Piper text-to-speech worker."""

from __future__ import annotations

import subprocess
from typing import Any


class PiperWorker:
    """Runs Piper and optionally pipes generated audio to a playback command."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.binary_path = config.get("binary_path")
        self.voice_path = config.get("voice_path")
        self.output_file = config.get("output_file", "kiosk/data/last_response.wav")
        self.playback_command = config.get("playback_command", ["aplay"])
        self.extra_args = config.get("extra_args", [])

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        if not self.binary_path or not self.voice_path:
            raise RuntimeError("Configure tts.binary_path and tts.voice_path before speech output")

        command = [
            self.binary_path,
            "--model",
            self.voice_path,
            "--output_file",
            self.output_file,
            *self.extra_args,
        ]
        subprocess.run(command, input=text, check=True, text=True)

        if self.playback_command:
            subprocess.run([*self.playback_command, self.output_file], check=True)

