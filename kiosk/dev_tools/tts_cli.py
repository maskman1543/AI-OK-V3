"""Development CLI for Piper text-to-speech output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kiosk.stt_ollama_bridge import load_config
from kiosk.tts.piper_worker import PiperConfigError, PiperWorker


def run_tts(
    config_path: str | Path,
    text: str,
    output_file: str | Path | None,
    no_play: bool,
) -> Path:
    config = load_config(config_path)
    tts_config = dict(config.get("tts", {}))

    if output_file is not None:
        tts_config["output_file"] = str(output_file)
    if no_play:
        tts_config["playback_command"] = []

    worker = PiperWorker(tts_config)
    worker.speak(text)
    return Path(tts_config.get("output_file", "kiosk/data/last_response.wav"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate speech with the configured TTS engine")
    parser.add_argument("--config", default="kiosk/config.yaml", help="Path to kiosk config YAML")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--output", default=None, help="WAV file path to write")
    parser.add_argument("--no-play", action="store_true", help="Generate the WAV without playing it")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args()
    try:
        output_path = run_tts(args.config, args.text, args.output, args.no_play)
    except PiperConfigError as exc:
        raise SystemExit(f"TTS setup is incomplete.\n{exc}") from None
    print(f"Wrote: {output_path}")


if __name__ == "__main__":
    main()
