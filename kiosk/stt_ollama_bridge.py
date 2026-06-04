"""Reusable Whisper STT -> Ollama bridge for CLI and web integrations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional runtime dependency
    yaml = None

from kiosk.llm.ollama_worker import OllamaWorker
from kiosk.rag.embedder import SentenceTransformerEmbedder
from kiosk.rag.index import ChromaVectorIndex, VectorIndex
from kiosk.rag.retriever import Retriever
from kiosk.stt.whisper_worker import WhisperWorker


@dataclass
class SttOllamaResult:
    transcript: str
    answer: str
    transcription_seconds: float
    llm_seconds: float


def load_config(config_path: str | Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("Install PyYAML to load kiosk/config.yaml")

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing kiosk config: {path}")

    with path.open("r", encoding="utf-8") as config_file:
        loaded = yaml.safe_load(config_file) or {}
    if not isinstance(loaded, dict):
        raise ValueError("kiosk config must be a YAML mapping")
    return loaded


def build_prompt(transcript: str, context: list[dict[str, Any]] | None = None) -> str:
    context = context or []
    context_block = ""
    if context:
        snippets = []
        for index, hit in enumerate(context, start=1):
            source = hit.get("metadata", {}).get("source", "knowledge base")
            snippets.append(f"[{index}] Source: {source}\n{hit.get('text', '')}")
        context_block = (
            "Use this knowledge-base context when it is relevant. "
            "If it is not relevant, answer normally and do not mention it.\n\n"
            + "\n\n".join(snippets)
            + "\n\n"
        )

    return (
        "Answer the user's spoken message once, clearly and briefly. "
        "Do not repeat the transcript. Do not invent facts.\n\n"
        f"{context_block}"
        f"User transcript: {transcript}\n\n"
        "Answer:"
    )


class SttOllamaBridge:
    """Keeps STT and Ollama workers together for repeated requests."""

    def __init__(
        self,
        config_path: str | Path = "kiosk/config.yaml",
        model_override: str | None = None,
    ) -> None:
        self.config = load_config(config_path)
        self.stt = WhisperWorker(self.config.get("stt", {}))

        ollama_config = dict(self.config.get("ollama", {}))
        if model_override:
            ollama_config["model"] = model_override
        self.llm = OllamaWorker(ollama_config)
        self.retriever = self._build_retriever()

    def answer_audio_file(self, audio_path: str | Path) -> SttOllamaResult:
        transcription_start = perf_counter()
        transcript = self.stt.transcribe(audio_path)
        transcription_seconds = perf_counter() - transcription_start
        return self.answer_transcript(
            transcript,
            transcription_seconds=transcription_seconds,
        )

    def answer_transcript(
        self,
        transcript: str,
        transcription_seconds: float = 0.0,
    ) -> SttOllamaResult:
        transcript = transcript.strip()
        if not transcript:
            raise RuntimeError("Transcript is empty; nothing to send to Ollama")

        context = self._retrieve_context(transcript)
        llm_start = perf_counter()
        answer = self.llm.generate(build_prompt(transcript, context=context))
        llm_seconds = perf_counter() - llm_start
        return SttOllamaResult(
            transcript=transcript,
            answer=answer,
            transcription_seconds=transcription_seconds,
            llm_seconds=llm_seconds,
        )

    def _build_retriever(self) -> Retriever | None:
        rag_config = self.config.get("rag", {})
        index_path = Path(rag_config.get("index_path", "kiosk/data/chroma"))
        if not index_path.exists():
            return None

        embedder = SentenceTransformerEmbedder(rag_config.get("embedding_model"))
        store = rag_config.get("store", "chroma")
        if store == "json":
            index = VectorIndex.load(index_path)
        else:
            index = ChromaVectorIndex.load(
                index_path,
                collection_name=rag_config.get("collection_name", "kiosk_kb"),
            )
        return Retriever(embedder, index, top_k=rag_config.get("top_k", 4))

    def _retrieve_context(self, transcript: str) -> list[dict[str, Any]]:
        if self.retriever is None:
            return []
        min_score = self.config.get("thresholds", {}).get("min_retrieval_score", 0.2)
        try:
            return [hit for hit in self.retriever.retrieve(transcript) if hit["score"] >= min_score]
        except RuntimeError:
            return []
