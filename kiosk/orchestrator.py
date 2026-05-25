"""Main pipeline state machine for the kiosk assistant."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover - optional runtime dependency
    yaml = None

from kiosk.llm.llama_worker import LlamaWorker
from kiosk.rag.embedder import SentenceTransformerEmbedder
from kiosk.rag.index import VectorIndex
from kiosk.rag.retriever import Retriever
from kiosk.stt.whisper_worker import WhisperWorker
from kiosk.tts.piper_worker import PiperWorker


TokenCallback = Callable[[str], None]


@dataclass
class PipelineResult:
    """Final output from one kiosk request."""

    transcript: str
    answer: str
    sources: list[dict[str, Any]]


class KioskOrchestrator:
    """Coordinates STT, retrieval, LLM generation, and TTS."""

    def __init__(
        self,
        config_path: str | Path = "kiosk/config.yaml",
        token_callback: TokenCallback | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config(self.config_path)
        self.token_callback = token_callback

        rag_config = self.config.get("rag", {})
        self.stt = WhisperWorker(self.config.get("stt", {}))
        self.embedder = SentenceTransformerEmbedder(rag_config.get("embedding_model"))
        self.index = VectorIndex.load(rag_config.get("index_path", "kiosk/data/index.json"))
        self.retriever = Retriever(self.embedder, self.index, top_k=rag_config.get("top_k", 4))
        self.llm = LlamaWorker(self.config.get("llm", {}))
        self.tts = PiperWorker(self.config.get("tts", {}))

    def run_audio_file(self, audio_path: str | Path, speak: bool = True) -> PipelineResult:
        """Process one recorded utterance and optionally speak the answer."""

        transcript = self.stt.transcribe(audio_path)
        sources = self.retriever.retrieve(transcript)
        prompt = self._build_prompt(transcript, sources)
        answer = self.llm.generate(prompt, token_callback=self.token_callback)

        if speak:
            self.tts.speak(answer)

        return PipelineResult(transcript=transcript, answer=answer, sources=sources)

    @staticmethod
    def _load_config(config_path: Path) -> dict[str, Any]:
        if not config_path.exists():
            raise FileNotFoundError(f"Missing kiosk config: {config_path}")
        if yaml is None:
            raise RuntimeError("Install PyYAML to load kiosk/config.yaml")
        with config_path.open("r", encoding="utf-8") as config_file:
            loaded = yaml.safe_load(config_file) or {}
        if not isinstance(loaded, dict):
            raise ValueError("kiosk config must be a YAML mapping")
        return loaded

    @staticmethod
    def _build_prompt(query: str, sources: list[dict[str, Any]]) -> str:
        context = "\n\n".join(
            f"[{idx + 1}] {source.get('text', '')}" for idx, source in enumerate(sources)
        )
        return (
            "Answer the user's question using only the context below. "
            "If the answer is not in the context, say you do not know.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n"
            "Answer:"
        )


def main() -> None:
    raise SystemExit("Instantiate KioskOrchestrator from your kiosk UI or microphone loop.")


if __name__ == "__main__":
    main()

