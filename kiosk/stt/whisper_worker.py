"""Whisper speech-to-text worker.

The worker is CLI-first for early integration testing, but the public methods
are ordinary Python calls so a future web UI can reuse the same STT path.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional runtime dependency
    yaml = None


class WhisperWorker:
    """Records microphone audio and transcribes it with a local Whisper CLI."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.engine = config.get("engine", "openai-whisper")
        self.cli_path = config.get("cli_path") or config.get("binary_path") or "whisper"
        self.model_name = config.get("model_name", "base")
        self.model_dir = config.get("model_dir")
        self.model_path = config.get("model_path")
        self.ffmpeg_path = config.get("ffmpeg_path")
        self.language = config.get("language", "en")
        self.task = config.get("task", "transcribe")
        self.sample_rate = int(config.get("sample_rate", 16000))
        self.channels = int(config.get("channels", 1))
        self.sample_width = int(config.get("sample_width", 2))
        self.recordings_dir = Path(config.get("recordings_dir", "kiosk/data/recordings"))
        self.extra_args = config.get("extra_args", [])

    @classmethod
    def from_config_file(cls, config_path: str | Path = "kiosk/config.yaml") -> "WhisperWorker":
        """Create a worker from the shared kiosk YAML config."""

        if yaml is None:
            raise RuntimeError("Install PyYAML to load kiosk/config.yaml")

        with Path(config_path).open("r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        return cls(config.get("stt", {}))

    def _get_native_sample_rate(self, device: int | str | None) -> int:
        """Fetch the hardware's native sample rate to prevent PortAudio crashes."""
        import sounddevice as sd
        if device is None:
            device_info = sd.query_devices(kind='input')
        else:
            device_info = sd.query_devices(device)
        return int(device_info['default_samplerate'])

    def _resample_to_target(self, output_path: Path, recorded_sr: int) -> Path:
        """Resample the recorded audio to the target Whisper sample rate (16000) if necessary."""
        if recorded_sr == self.sample_rate:
            return output_path
            
        ffmpeg_path = self._resolve_ffmpeg()
        if not ffmpeg_path:
            # If no FFmpeg is found, return the raw file and hope the engine handles it
            return output_path
            
        temp_path = output_path.with_name(f"{output_path.stem}_resampled{output_path.suffix}")
        
        command = [
            ffmpeg_path,
            "-y",               # Overwrite without asking
            "-i", str(output_path),
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            str(temp_path)
        ]
        
        try:
            subprocess.run(command, check=True, capture_output=True)
            temp_path.replace(output_path) # Overwrite the original with the resampled 16k version
        except subprocess.CalledProcessError as e:
            print(f"[WhisperWorker] FFmpeg resampling failed: {e.stderr.decode('utf-8', errors='ignore')}")
            if temp_path.exists():
                temp_path.unlink()
                
        return output_path

    def record_microphone(
        self,
        output_path: str | Path | None = None,
        duration_seconds: float = 5.0,
        device: int | str | None = None,
    ) -> Path:
        """Capture microphone input into a mono WAV file."""

        try:
            import sounddevice as sd
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise RuntimeError(
                "Install sounddevice for microphone capture: pip install sounddevice"
            ) from exc

        if duration_seconds <= 0:
            raise ValueError("Recording duration must be greater than zero")

        output = Path(output_path) if output_path else self._default_recording_path()
        output.parent.mkdir(parents=True, exist_ok=True)
        input_device = _parse_device(device)
        
        # Dynamically adapt to hardware limitations
        native_sr = self._get_native_sample_rate(input_device)

        frames_remaining = int(duration_seconds * native_sr)
        block_size = min(native_sr, frames_remaining)

        with wave.open(str(output), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(native_sr)

            def callback(indata, frame_count, _time, status) -> None:
                nonlocal frames_remaining
                if status:
                    print(status)
                wav_file.writeframes(indata)
                frames_remaining -= frame_count
                if frames_remaining <= 0:
                    raise sd.CallbackStop

            with sd.RawInputStream(
                samplerate=native_sr,
                blocksize=block_size,
                device=input_device,
                channels=self.channels,
                dtype="int16",
                callback=callback,
            ):
                sd.sleep(int(duration_seconds * 1000) + 250)

        # Seamlessly convert to 16k for Whisper
        return self._resample_to_target(output, native_sr)

    def record_until_stop(
        self,
        stop_event: Any,
        output_path: str | Path | None = None,
        device: int | str | None = None,
    ) -> Path:
        """Capture microphone input into a WAV file until stop_event is set."""

        try:
            import sounddevice as sd
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise RuntimeError(
                "Install sounddevice for microphone capture: pip install sounddevice"
            ) from exc

        output = Path(output_path) if output_path else self._default_recording_path()
        output.parent.mkdir(parents=True, exist_ok=True)
        input_device = _parse_device(device)
        
        native_sr = self._get_native_sample_rate(input_device)

        with wave.open(str(output), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(native_sr)

            def callback(indata, _frame_count, _time, status) -> None:
                if status:
                    print(status)
                wav_file.writeframes(indata)

            block_size = min(1024, native_sr)
            with sd.RawInputStream(
                samplerate=native_sr,
                blocksize=block_size,
                device=input_device,
                channels=self.channels,
                dtype="int16",
                callback=callback,
            ):
                while not stop_event.is_set():
                    sd.sleep(100)

        return self._resample_to_target(output, native_sr)

    def transcribe_microphone(
        self,
        duration_seconds: float = 5.0,
        output_path: str | Path | None = None,
        device: int | str | None = None,
    ) -> str:
        """Record microphone audio and return the transcript."""

        audio_path = self.record_microphone(output_path, duration_seconds, device=device)
        return self.transcribe(audio_path)

    def transcribe(self, audio_path: str | Path) -> str:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if self.engine == "openai-whisper":
            return self._transcribe_openai_whisper(audio_path)
        if self.engine == "whisper.cpp":
            return self._transcribe_whisper_cpp(audio_path)
        raise ValueError(f"Unsupported Whisper engine: {self.engine}")

    def _transcribe_openai_whisper(self, audio_path: Path) -> str:
        cli_path = self._resolve_cli()
        ffmpeg_path = self._resolve_ffmpeg()
        if ffmpeg_path is None:
            raise RuntimeError(
                "ffmpeg is required by openai-whisper but was not found on PATH"
            )
        with tempfile.TemporaryDirectory(prefix="kiosk-whisper-") as output_dir:
            command = [
                cli_path,
                str(audio_path),
                "--model",
                self.model_name,
                "--task",
                self.task,
                "--output_format",
                "txt",
                "--output_dir",
                output_dir,
            ]
            if self.language:
                command.extend(["--language", self.language])
            if self.model_dir:
                command.extend(["--model_dir", self.model_dir])
            command.extend(self.extra_args)
            env = os.environ.copy()
            if ffmpeg_path:
                ffmpeg_dir = str(Path(ffmpeg_path).parent)
                env["PATH"] = f"{ffmpeg_dir}{os.pathsep}{env.get('PATH', '')}"
            completed = subprocess.run(command, check=True, capture_output=True, text=True, env=env)

            transcript_file = Path(output_dir) / f"{audio_path.stem}.txt"
            if transcript_file.exists():
                return transcript_file.read_text(encoding="utf-8").strip()
            return completed.stdout.strip()

    def _resolve_ffmpeg(self) -> str | None:
        if self.ffmpeg_path:
            configured = Path(self.ffmpeg_path)
            if configured.exists():
                return str(configured)
        return shutil.which("ffmpeg")

    def _transcribe_whisper_cpp(self, audio_path: Path) -> str:
        cli_path = self._resolve_cli()
        if not self.model_path:
            raise RuntimeError("Configure stt.model_path before whisper.cpp transcription")

        command = [
            cli_path,
            "-m",
            self.model_path,
            "-f",
            str(audio_path),
            "-l",
            self.language,
            "-nt",
            *self.extra_args,
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return completed.stdout.strip()

    def _resolve_cli(self) -> str:
        resolved = shutil.which(self.cli_path)
        if resolved:
            return resolved
        configured = Path(self.cli_path)
        if configured.exists():
            return str(configured)
            
        # Check Linux/macOS venv path
        linux_cli = Path("venv") / "bin" / self.cli_path
        if linux_cli.exists():
            return str(linux_cli)
            
        # Check Windows venv path
        win_cli = Path("venv") / "Scripts" / f"{self.cli_path}.exe"
        if win_cli.exists():
            return str(win_cli)
            
        raise RuntimeError(f"Whisper CLI not found: {self.cli_path}")

    def _default_recording_path(self) -> Path:
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        return self.recordings_dir / "microphone_input.wav"


def list_input_devices() -> None:
    """Print available input devices for CLI setup."""

    try:
        import sounddevice as sd
    except ImportError as exc:  # pragma: no cover - depends on deployment
        raise RuntimeError("Install sounddevice to list microphone devices") from exc
    print(sd.query_devices())


def _parse_device(device: int | str | None) -> int | str | None:
    if isinstance(device, str) and device.isdigit():
        return int(device)
    return device


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kiosk Whisper STT utility")
    parser.add_argument("--config", default="kiosk/config.yaml", help="Path to kiosk config YAML")

    subparsers = parser.add_subparsers(dest="command", required=True)

    devices = subparsers.add_parser("devices", help="List microphone input devices")
    devices.set_defaults(command="devices")

    record = subparsers.add_parser("record", help="Record microphone audio to a WAV file")
    record.add_argument("--duration", type=float, default=5.0)
    record.add_argument("--output", default=None)
    record.add_argument("--device", default=None)

    transcribe = subparsers.add_parser("transcribe", help="Transcribe an existing audio file")
    transcribe.add_argument("audio_path")

    listen = subparsers.add_parser("listen", help="Record microphone audio and transcribe it")
    listen.add_argument("--duration", type=float, default=5.0)
    listen.add_argument("--output", default=None)
    listen.add_argument("--device", default=None)

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "devices":
        list_input_devices()
        return

    worker = WhisperWorker.from_config_file(args.config)

    if args.command == "record":
        output = worker.record_microphone(args.output, args.duration, device=args.device)
        print(output)
        return

    if args.command == "transcribe":
        print(worker.transcribe(args.audio_path))
        return

    if args.command == "listen":
        print(worker.transcribe_microphone(args.duration, args.output, device=args.device))
        return


if __name__ == "__main__":
    main()