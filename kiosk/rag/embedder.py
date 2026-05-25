"""Embedding adapters for retrieval."""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per input text."""


class SentenceTransformerEmbedder:
    """Lazy sentence-transformers embedder."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on deployment
                raise RuntimeError("Install sentence-transformers to create embeddings") from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model

