"""GUI-ready voice assistant orchestration.

This module is the integration boundary for apps that need microphone input,
Whisper transcription, Ollama responses, and Piper speech output.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Generic, TypeVar


def find_project_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "kiosk" / "config.yaml").exists():
            return path
    raise RuntimeError("Could not find project root containing kiosk/config.yaml")


if __package__ in {None, ""}:
    sys.path.insert(0, str(find_project_root(Path(__file__).resolve())))

from kiosk.stt.whisper_worker import list_input_devices
from kiosk.stt_ollama_bridge import SttOllamaBridge, SttOllamaResult, load_config
from kiosk.tts.piper_worker import PiperConfigError, PiperWorker


PROJECT_ROOT = find_project_root(Path(__file__).resolve())
DEFAULT_CONFIG = PROJECT_ROOT / "kiosk" / "config.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "kiosk" / "data" / "recordings" / "gui_voice_input.wav"

T = TypeVar("T")


class RecordingError(RuntimeError):
    """Raised when microphone capture produced no usable audio."""


@dataclass
class TimedResult(Generic[T]):
    value: T
    seconds: float


@dataclass
class AudioStats:
    frames: int
    frame_rate: int
    channels: int
    sample_width: int
    duration_seconds: float
    rms: int
    peak: int


@dataclass
class RuntimeBreakdown:
    setup_seconds: float = 0.0
    recording_seconds: float = 0.0
    transcription_seconds: float = 0.0
    llm_seconds: float = 0.0
    tts_seconds: float = 0.0
    total_seconds: float = 0.0

    def rows(self) -> list[tuple[str, float]]:
        rows = [
            ("setup", self.setup_seconds),
            ("recording", self.recording_seconds),
            ("transcription", self.transcription_seconds),
            ("llm", self.llm_seconds),
        ]
        if self.tts_seconds:
            rows.append(("tts", self.tts_seconds))
        rows.append(("total", self.total_seconds))
        return rows


@dataclass
class VoiceAssistantResult:
    transcript: str
    answer: str
    audio_path: Path | None
    audio_stats: AudioStats | None
    runtimes: RuntimeBreakdown


def timed(action: Callable[[], T]) -> TimedResult[T]:
    start = perf_counter()
    value = action()
    return TimedResult(value=value, seconds=perf_counter() - start)


def calculate_pcm_level(audio: bytes, sample_width: int) -> tuple[int, int]:
    if not audio:
        return 0, 0
    if sample_width == 1:
        samples = [sample - 128 for sample in audio]
    elif sample_width == 2:
        samples_array = array("h")
        samples_array.frombytes(audio)
        if sys.byteorder != "little":
            samples_array.byteswap()
        samples = samples_array
    else:
        return 0, max(audio)

    peak = max(abs(sample) for sample in samples)
    rms = int((sum(sample * sample for sample in samples) / len(samples)) ** 0.5)
    return rms, peak


def inspect_wav(audio_path: str | Path) -> AudioStats:
    with wave.open(str(audio_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        frame_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        audio = wav_file.readframes(frames)

    duration_seconds = frames / frame_rate if frame_rate else 0.0
    rms, peak = calculate_pcm_level(audio, sample_width)
    return AudioStats(
        frames=frames,
        frame_rate=frame_rate,
        channels=channels,
        sample_width=sample_width,
        duration_seconds=duration_seconds,
        rms=rms,
        peak=peak,
    )


def validate_recording(audio_path: str | Path, min_duration_seconds: float = 0.25) -> AudioStats:
    stats = inspect_wav(audio_path)
    if stats.duration_seconds < min_duration_seconds or stats.peak == 0:
        raise RecordingError(
            "Recording is empty or silent. "
            f"Duration: {stats.duration_seconds:.2f}s, peak: {stats.peak}, rms: {stats.rms}."
        )
    return stats


class VoiceAssistantOrchestrator:
    """Reusable service for GUI and CLI voice assistant flows."""

    def __init__(
        self,
        config_path: str | Path = DEFAULT_CONFIG,
        model_override: str | None = None,
        default_output: str | Path = DEFAULT_OUTPUT,
    ) -> None:
        self.project_root = PROJECT_ROOT
        self.config_path = Path(config_path)
        self.default_output = Path(default_output)
        self.model_override = model_override

        # Existing config paths are relative to the repo root.
        os.chdir(self.project_root)

        bridge_result = timed(lambda: SttOllamaBridge(self.config_path, model_override=model_override))
        self.bridge = bridge_result.value
        self.config = load_config(self.config_path)
        self.tts = PiperWorker(self.config.get("tts", {}))
        self.setup_seconds = bridge_result.seconds

        self._recording_stop: threading.Event | None = None
        self._recording_thread: threading.Thread | None = None
        self._recording_path: Path | None = None
        self._recording_error: BaseException | None = None
        self._recording_started_at: float | None = None
        self._recording_seconds: float = 0.0

    def start_recording(
        self,
        output_path: str | Path | None = None,
        device: int | str | None = None,
    ) -> Path:
        """Start push-to-talk recording in a background thread."""

        if self._recording_thread and self._recording_thread.is_alive():
            raise RuntimeError("Recording is already running")

        self._recording_stop = threading.Event()
        self._recording_path = Path(output_path) if output_path else self.default_output
        self._recording_error = None
        self._recording_started_at = perf_counter()

        def record() -> None:
            try:
                self.bridge.stt.record_until_stop(
                    self._recording_stop,
                    output_path=self._recording_path,
                    device=device,
                )
            except BaseException as exc:  # keep GUI thread in control of reporting
                self._recording_error = exc

        self._recording_thread = threading.Thread(target=record, daemon=True)
        self._recording_thread.start()
        return self._recording_path

    def stop_recording(self, timeout_seconds: float = 10.0) -> Path:
        """Stop push-to-talk recording and return the WAV path."""

        if not self._recording_thread or not self._recording_stop or not self._recording_path:
            raise RuntimeError("Recording has not been started")

        self._recording_stop.set()
        self._recording_thread.join(timeout=timeout_seconds)
        if self._recording_thread.is_alive():
            raise RuntimeError("Recording did not stop before timeout")
        if self._recording_error:
            raise self._recording_error

        if self._recording_started_at is not None:
            self._recording_seconds = perf_counter() - self._recording_started_at
        return self._recording_path

    def record_fixed(
        self,
        duration_seconds: float,
        output_path: str | Path | None = None,
        device: int | str | None = None,
    ) -> Path:
        """Record a fixed-duration WAV file for non push-to-talk UIs."""

        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than zero")
        result = timed(
            lambda: self.bridge.stt.record_microphone(
                output_path=output_path or self.default_output,
                duration_seconds=duration_seconds,
                device=device,
            )
        )
        self._recording_seconds = result.seconds
        return result.value

    def process_audio_file(self, audio_path: str | Path, speak: bool = True) -> VoiceAssistantResult:
        """Transcribe a WAV file, ask Ollama, optionally speak the answer."""

        total_start = perf_counter()
        audio = Path(audio_path)
        stats = validate_recording(audio)

        transcript_result = timed(lambda: self.bridge.stt.transcribe(audio))
        transcript = transcript_result.value.strip()
        if not transcript:
            raise RecordingError("Transcript is empty; try recording again closer to the microphone.")

        answer_result = timed(lambda: self.bridge.answer_transcript(transcript))
        tts_seconds = self.speak(answer_result.value.answer) if speak else 0.0

        return self._build_result(
            bridge_result=answer_result.value,
            audio_path=audio,
            audio_stats=stats,
            recording_seconds=self._recording_seconds,
            transcription_seconds=transcript_result.seconds,
            llm_seconds=answer_result.seconds,
            tts_seconds=tts_seconds,
            total_seconds=perf_counter() - total_start,
        )

    def process_transcript(self, transcript: str, speak: bool = True) -> VoiceAssistantResult:
        """Ask Ollama from typed text, optionally speak the answer."""

        total_start = perf_counter()
        answer_result = timed(lambda: self.bridge.answer_transcript(transcript))
        tts_seconds = self.speak(answer_result.value.answer) if speak else 0.0

        return self._build_result(
            bridge_result=answer_result.value,
            audio_path=None,
            audio_stats=None,
            recording_seconds=0.0,
            transcription_seconds=0.0,
            llm_seconds=answer_result.seconds,
            tts_seconds=tts_seconds,
            total_seconds=perf_counter() - total_start,
        )

    def speak(self, text: str) -> float:
        """Speak text through configured TTS and return elapsed seconds."""

        try:
            return timed(lambda: self.tts.speak(text)).seconds
        except PiperConfigError:
            raise
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise PiperConfigError(f"TTS failed. Check the `tts` section in kiosk/config.yaml.\n{exc}") from exc

    def _build_result(
        self,
        bridge_result: SttOllamaResult,
        audio_path: Path | None,
        audio_stats: AudioStats | None,
        recording_seconds: float,
        transcription_seconds: float,
        llm_seconds: float,
        tts_seconds: float,
        total_seconds: float,
    ) -> VoiceAssistantResult:
        return VoiceAssistantResult(
            transcript=bridge_result.transcript,
            answer=bridge_result.answer,
            audio_path=audio_path,
            audio_stats=audio_stats,
            runtimes=RuntimeBreakdown(
                setup_seconds=self.setup_seconds,
                recording_seconds=recording_seconds,
                transcription_seconds=transcription_seconds,
                llm_seconds=llm_seconds,
                tts_seconds=tts_seconds,
                total_seconds=total_seconds,
            ),
        )


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def print_runtime_table(rows: list[tuple[str, float]]) -> None:
    print()
    print("Runtimes:")
    for label, seconds in rows:
        print(f"  {label:<16} {format_seconds(seconds)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record voice, transcribe it, send it to Ollama, and print runtimes."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to kiosk config YAML")
    parser.add_argument("--model", default=None, help="Override configured Ollama model")
    parser.add_argument(
        "--record",
        type=float,
        default=None,
        help="Record a fixed number of seconds instead of push-to-talk",
    )
    parser.add_argument(
        "--push-to-talk",
        action="store_true",
        help="Press Enter to start recording, then Enter again to stop. This is the default.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Where to save the recorded WAV file",
    )
    parser.add_argument("--device", default=None, help="Input device id or name")
    parser.add_argument("--devices", action="store_true", help="List input devices and exit")
    parser.set_defaults(speak=True)
    parser.add_argument(
        "--speak",
        dest="speak",
        action="store_true",
        help="Speak the LLM response with configured TTS. This is the default.",
    )
    parser.add_argument(
        "--no-speak",
        dest="speak",
        action="store_false",
        help="Do not run text-to-speech after the LLM response",
    )
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args()
    if args.devices:
        list_input_devices()
        return

    assistant = VoiceAssistantOrchestrator(args.config, model_override=args.model)

    try:
        if args.record is not None:
            audio_path = assistant.record_fixed(args.record, output_path=args.output, device=args.device)
        else:
            input("Press Enter to start recording...")
            audio_path = assistant.start_recording(output_path=args.output, device=args.device)
            print("Recording. Press Enter to stop.")
            input()
            assistant.stop_recording()

        print(f"Saved audio: {audio_path}")
        result = assistant.process_audio_file(audio_path, speak=args.speak)
    except (RecordingError, PiperConfigError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None

    if result.audio_stats:
        print(
            "Audio stats: "
            f"{result.audio_stats.duration_seconds:.2f}s, "
            f"{result.audio_stats.frame_rate} Hz, "
            f"{result.audio_stats.channels} channel(s), "
            f"peak {result.audio_stats.peak}, rms {result.audio_stats.rms}"
        )
    print()
    print("Transcript:")
    print(result.transcript)
    print()
    print("LLM response:")
    print(result.answer)
    print_runtime_table(result.runtimes.rows())


if __name__ == "__main__":
    main()
