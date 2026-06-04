"""JSON command bridge used by the Electron kiosk UI."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from kiosk.ingestion.ingest import ingest_paths
from kiosk.orchestrator import DEFAULT_CONFIG, VoiceAssistantOrchestrator
from kiosk.stt_ollama_bridge import load_config
from kiosk.tts.piper_worker import PiperWorker


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _log(message: str) -> None:
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    print(f"[ui_bridge] {message}", file=sys.stderr, flush=True)


def _result_payload(payload: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(payload, ensure_ascii=False))


def _runtime_payload(result) -> dict[str, float]:
    return {label: seconds for label, seconds in result.runtimes.rows()}


def ask_text(text: str, speak: bool = True) -> dict[str, Any]:
    _log(f"ask: {text[:80]!r}, speak={speak}")
    assistant = VoiceAssistantOrchestrator(config_path=DEFAULT_CONFIG)
    result = assistant.process_transcript(text, speak=speak)
    _log("ask complete")
    return {
        "ok": True,
        "transcript": result.transcript,
        "answer": result.answer,
        "audioPath": str(result.audio_path) if result.audio_path else None,
        "runtimes": _runtime_payload(result),
    }


def listen_once(duration_seconds: float, speak: bool = False) -> dict[str, Any]:
    _log(f"listen: duration={duration_seconds}, speak={speak}")
    assistant = VoiceAssistantOrchestrator(config_path=DEFAULT_CONFIG)
    audio_path = assistant.record_fixed(duration_seconds)
    result = assistant.process_audio_file(audio_path, speak=speak)
    _log("listen complete")
    return {
        "ok": True,
        "transcript": result.transcript,
        "answer": result.answer,
        "audioPath": str(result.audio_path) if result.audio_path else None,
        "runtimes": _runtime_payload(result),
    }


def record_until_stopped(device: int | str | None = 2) -> dict[str, Any]:
    _log(f"push-to-talk recording started, device={device}")
    assistant = VoiceAssistantOrchestrator(config_path=DEFAULT_CONFIG)
    audio_path = assistant.start_recording(device=device)
    sys.stdin.readline()
    assistant.stop_recording()
    transcript = assistant.bridge.stt.transcribe(audio_path).strip()
    if not transcript:
        raise RuntimeError("Transcript is empty; try recording again closer to the microphone.")
    _log("push-to-talk transcription complete")
    return {
        "ok": True,
        "transcript": transcript,
        "audioPath": str(audio_path),
    }


def ingest_documents(paths: list[str]) -> dict[str, Any]:
    _log(f"ingest starting: {len(paths)} file(s)")
    for path in paths:
        _log(f"  {path}")
    config = load_config(DEFAULT_CONFIG)
    rag_config = config.get("rag", {})
    chunk_count = ingest_paths(
        paths,
        index_path=rag_config.get("index_path", "kiosk/data/chroma"),
        embedding_model=rag_config.get("embedding_model"),
        store=rag_config.get("store", "chroma"),
        collection_name=rag_config.get("collection_name", "kiosk_kb"),
        converted_text_dir=rag_config.get("converted_text_dir", "kiosk/data/converted_text"),
    )
    _log(f"ingest complete: {chunk_count} chunk(s)")
    return {
        "ok": True,
        "chunkCount": chunk_count,
        "paths": paths,
    }


def speak_text(text: str) -> dict[str, Any]:
    _log(f"speak: {text[:80]!r}")
    config = load_config(DEFAULT_CONFIG)
    PiperWorker(config.get("tts", {})).speak(text)
    _log("speak complete")
    return {"ok": True}


def status() -> dict[str, Any]:
    _log("status requested")
    config = load_config(DEFAULT_CONFIG)
    return {
        "ok": True,
        "ollama": config.get("ollama", {}),
        "tts": {
            "engine": config.get("tts", {}).get("engine"),
            "outputFile": config.get("tts", {}).get("output_file"),
        },
        "rag": config.get("rag", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Electron UI bridge for AI-OK")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("--text", required=True)
    ask_parser.set_defaults(speak=True)
    ask_parser.add_argument("--speak", dest="speak", action="store_true")
    ask_parser.add_argument("--no-speak", dest="speak", action="store_false")

    listen_parser = subparsers.add_parser("listen")
    listen_parser.add_argument("--duration", type=float, default=5.0)
    listen_parser.set_defaults(speak=False)
    listen_parser.add_argument("--speak", dest="speak", action="store_true")
    listen_parser.add_argument("--no-speak", dest="speak", action="store_false")

    record_parser = subparsers.add_parser("record-transcribe")
    record_parser.add_argument("--device", default=2)

    speak_parser = subparsers.add_parser("speak")
    speak_parser.add_argument("--text", required=True)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("paths", nargs="+")

    subparsers.add_parser("status")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "ask":
            payload = ask_text(args.text, speak=args.speak)
        elif args.command == "listen":
            payload = listen_once(args.duration, speak=args.speak)
        elif args.command == "record-transcribe":
            payload = record_until_stopped(device=args.device)
        elif args.command == "speak":
            payload = speak_text(args.text)
        elif args.command == "ingest":
            payload = ingest_documents(args.paths)
        elif args.command == "status":
            payload = status()
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception as exc:
        _log("command failed")
        traceback.print_exc(file=sys.stderr)
        payload = {"ok": False, "error": str(exc)}
    _result_payload(payload)


if __name__ == "__main__":
    main()
