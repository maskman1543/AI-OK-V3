"""Piper text-to-speech worker."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any


class PiperConfigError(RuntimeError):
    """Raised when Piper cannot run because required config is missing."""


def piper_config_help() -> str:
    return (
        "Configure Piper TTS in kiosk/config.yaml:\n"
        "  tts.binary_path: full path to piper.exe\n"
        "  tts.voice_path: full path to a Piper .onnx voice file"
    )


class PiperWorker:
    """Runs configured text-to-speech output and optional audio playback."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.engine = config.get("engine", "piper")
        self.binary_path = config.get("binary_path")
        self.voice_path = config.get("voice_path")
        self.output_file = config.get("output_file", "kiosk/data/last_response.wav")
        self.playback_command = config.get("playback_command", ["aplay"])
        self.extra_args = config.get("extra_args", [])

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.engine == "windows-sapi":
            self._speak_windows_sapi(text, output_path)
            self._play(output_path)
            return

        if self.engine != "piper":
            raise PiperConfigError(f"Unsupported TTS engine: {self.engine}")

        if not self.binary_path or not self.voice_path:
            raise PiperConfigError(piper_config_help())

        command = [
            self.binary_path,
            "--model",
            self.voice_path,
            "--output_file",
            str(output_path),
            *self.extra_args,
        ]
        subprocess.run(command, input=text, check=True, text=True)
        self._play(output_path)

    def _play(self, output_path: Path) -> None:
        if self.playback_command:
            if isinstance(self.playback_command, str):
                playback_command = [self.playback_command]
            else:
                playback_command = list(self.playback_command)
            subprocess.run([*playback_command, str(output_path)], check=True)

    def _speak_windows_sapi(self, text: str, output_path: Path) -> None:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "& { param($outFile) "
                "Add-Type -AssemblyName System.Speech; "
                "$speechText = [Console]::In.ReadToEnd(); "
                "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$synth.SetOutputToWaveFile($outFile); "
                "$synth.Speak($speechText); "
                "$synth.Dispose() "
                "}"
            ),
            str(output_path),
        ]
        subprocess.run(command, input=text, check=True, text=True)
