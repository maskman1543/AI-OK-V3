"""Top-k chunk retrieval."""

from __future__ import annotations

from typing import Any

from kiosk.rag.embedder import Embedder
from kiosk.rag.index import VectorIndex


class Retriever:
    def __init__(self, embedder: Embedder, index: VectorIndex, top_k: int = 4) -> None:
        self.embedder = embedder
        self.index = index
        self.top_k = top_k

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        embedding = self.embedder.embed([query])[0]
        return [
            {
                "id": hit.id,
                "text": hit.text,
                "score": hit.score,
                "metadata": hit.metadata,
            }
            for hit in self.index.search(embedding, top_k=self.top_k)
        ]

