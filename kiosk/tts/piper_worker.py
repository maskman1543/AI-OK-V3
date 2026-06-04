"""Piper text-to-speech worker."""

from __future__ import annotations

import platform
from pathlib import Path
import shutil
import subprocess
from typing import Any


class PiperConfigError(RuntimeError):
    """Raised when Piper cannot run because required config is missing."""


def piper_config_help() -> str:
    return (
        "Configure TTS in kiosk/config.yaml:\n"
        "  tts.engine: auto, windows-sapi, piper, espeak, or mms-cebuano\n"
        "  tts.binary_path: optional full path to Piper, or leave empty to auto-detect\n"
        "  tts.voice_path: full path to a Piper .onnx voice file\n"
        "For Raspberry Pi, install a Linux Piper binary named `piper` on PATH or in "
        "kiosk/models/piper/bin/piper."
    )


class PiperWorker:
    """Runs configured text-to-speech output and optional audio playback."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.engine = config.get("engine", "auto")
        self.binary_path = config.get("binary_path")
        self.voice_path = config.get("voice_path")
        self.model_name = config.get("model_name", "facebook/mms-tts-ceb")
        self.mms_language = config.get("mms_language", "ceb")
        self.local_files_only = bool(config.get("local_files_only", False))
        self.output_file = config.get("output_file", "kiosk/data/last_response.wav")
        self.playback_command = config.get("playback_command", "auto")
        self.extra_args = config.get("extra_args", [])

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        engine = self._resolve_engine()
        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if engine == "windows-sapi":
            self._speak_windows_sapi(text, output_path)
            self._play(output_path)
            return

        if engine == "espeak":
            self._speak_espeak(text)
            return

        if engine == "mms-cebuano":
            self._speak_mms_cebuano(text, output_path)
            self._play(output_path)
            return

        if engine != "piper":
            raise PiperConfigError(f"Unsupported TTS engine: {engine}")

        piper_binary = self._resolve_piper_binary()
        if not self.voice_path:
            raise PiperConfigError(piper_config_help())
        if not Path(self.voice_path).exists():
            raise PiperConfigError(f"Piper voice not found: {self.voice_path}")

        command = [
            piper_binary,
            "--model",
            self.voice_path,
            "--output_file",
            str(output_path),
            *self.extra_args,
        ]
        subprocess.run(command, input=text, check=True, text=True)
        self._play(output_path)

    def _resolve_engine(self) -> str:
        if self.engine != "auto":
            return self.engine
        if self.voice_path and Path(self.voice_path).exists():
            try:
                self._resolve_piper_binary()
            except PiperConfigError:
                pass
            else:
                return "piper"
        if platform.system() == "Windows":
            return "windows-sapi"
        if shutil.which("espeak-ng") or shutil.which("espeak"):
            return "espeak"
        raise PiperConfigError(piper_config_help())

    def _resolve_piper_binary(self) -> str:
        candidates: list[str | Path] = []
        if self.binary_path:
            candidates.append(self.binary_path)

        if platform.system() == "Windows":
            candidates.append(Path("kiosk/models/piper/bin/piper.exe"))
            executable_name = "piper.exe"
        else:
            candidates.append(Path("kiosk/models/piper/bin/piper"))
            executable_name = "piper"

        found_on_path = shutil.which(executable_name) or shutil.which("piper")
        if found_on_path:
            candidates.append(found_on_path)

        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                return str(path)

        raise PiperConfigError(f"Piper binary not found. {piper_config_help()}")

    def _play(self, output_path: Path) -> None:
        if not self.playback_command:
            return
        if self.playback_command == "auto":
            playback_command = self._default_playback_command()
        elif isinstance(self.playback_command, str):
            playback_command = [self.playback_command]
        else:
            playback_command = list(self.playback_command)
        subprocess.run([*playback_command, str(output_path)], check=True)

    def _default_playback_command(self) -> list[str]:
        if platform.system() == "Windows":
            return [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "& { param($wav) (New-Object Media.SoundPlayer $wav).PlaySync() }",
            ]
        for command in ("aplay", "paplay"):
            if shutil.which(command):
                return [command]
        raise PiperConfigError("No audio playback command found. Install `alsa-utils` for `aplay`.")

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

    def _speak_espeak(self, text: str) -> None:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not binary:
            raise PiperConfigError(piper_config_help())
        subprocess.run([binary, *self.extra_args, text], check=True, text=True)

    def _speak_mms_cebuano(self, text: str, output_path: Path) -> None:
        model_name = self.model_name
        if model_name == "facebook/mms-1b-l1107":
            model_name = "facebook/mms-tts-ceb"

        try:
            import torch
            from scipy.io.wavfile import write as write_wav
            from transformers import AutoTokenizer, VitsModel
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise PiperConfigError(
                "Install transformers, torch, and scipy to use tts.engine: mms-cebuano."
            ) from exc

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                local_files_only=self.local_files_only,
            )
            model = VitsModel.from_pretrained(
                model_name,
                local_files_only=self.local_files_only,
            )
        except Exception as exc:
            raise PiperConfigError(
                f"Could not load MMS Cebuano TTS model `{model_name}`. "
                "If this is the first run, set tts.local_files_only to false once "
                "or download the model before using offline mode."
            ) from exc

        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform
        audio = waveform.squeeze().cpu().numpy()
        sampling_rate = int(getattr(model.config, "sampling_rate", 16000))
        write_wav(output_path, sampling_rate, audio)
