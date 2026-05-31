"""Development CLI bridge for Whisper STT -> Ollama response generation."""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from kiosk.stt_ollama_bridge import SttOllamaBridge, SttOllamaResult, load_config
from kiosk.stt.whisper_worker import list_input_devices
from kiosk.tts.piper_worker import PiperConfigError, PiperWorker


def run_bridge(
    config_path: str | Path,
    audio_path: str | Path | None,
    transcript_text: str | None,
    model: str | None,
    record_seconds: float | None,
    record_output: str | Path | None,
    device: int | str | None,
    push_to_talk: bool,
) -> SttOllamaResult:
    bridge = SttOllamaBridge(config_path, model_override=model)

    if transcript_text is None:
        if push_to_talk:
            stop_event = threading.Event()
            input("Press Enter to start recording...")
            print("Recording. Press Enter to stop.")

            def wait_for_stop() -> None:
                input()
                stop_event.set()

            recorder = threading.Thread(
                target=wait_for_stop,
                daemon=True,
            )
            recorder.start()
            audio_path = bridge.stt.record_until_stop(
                stop_event,
                output_path=record_output,
                device=device,
            )
        elif record_seconds is not None:
            audio_path = bridge.stt.record_microphone(
                output_path=record_output,
                duration_seconds=record_seconds,
                device=device,
            )
        if audio_path is None:
            raise ValueError("Provide an audio path, --record, --push-to-talk, or --text")
        return bridge.answer_audio_file(audio_path)

    return bridge.answer_transcript(transcript_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Whisper STT output through Ollama")
    parser.add_argument("audio_path", nargs="?", help="Audio file to transcribe")
    parser.add_argument("--config", default="kiosk/config.yaml", help="Path to kiosk config YAML")
    parser.add_argument("--model", default=None, help="Override Ollama model name")
    parser.add_argument("--text", default=None, help="Skip STT and send this transcript to Ollama")
    parser.add_argument("--record", type=float, default=None, help="Record this many seconds of audio")
    parser.add_argument(
        "--push-to-talk",
        action="store_true",
        help="Press Enter to start recording, then Enter again to stop",
    )
    parser.add_argument("--output", default=None, help="WAV path for --record or --push-to-talk")
    parser.add_argument("--device", default=None, help="Input device id or name for recording")
    parser.add_argument("--devices", action="store_true", help="List input devices and exit")
    parser.add_argument("--speak", action="store_true", help="Speak the Ollama answer with TTS")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args()
    if args.devices:
        list_input_devices()
        return

    result = run_bridge(
        args.config,
        args.audio_path,
        args.text,
        args.model,
        args.record,
        args.output,
        args.device,
        args.push_to_talk,
    )
    print("Transcript:")
    print(result.transcript)
    print(f"Transcription time: {result.transcription_seconds:.2f}s")
    print()
    print("Ollama:")
    print(result.answer)
    print(f"LLM response time: {result.llm_seconds:.2f}s")

    if args.speak:
        config = load_config(args.config)
        try:
            PiperWorker(config.get("tts", {})).speak(result.answer)
        except PiperConfigError as exc:
            raise SystemExit(f"TTS setup is incomplete.\n{exc}") from None


if __name__ == "__main__":
    main()
