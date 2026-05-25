"""Vector index wrapper.

This file keeps the kiosk pipeline independent from the backing store. The
default JSON index is simple and portable; swap this class for ChromaDB or
FAISS when the deployment dependency is available.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SearchHit:
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorIndex:
    """Small cosine-similarity index persisted as JSON."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records or []

    @classmethod
    def load(cls, path: str | Path) -> "VectorIndex":
        index_path = Path(path)
        if not index_path.exists():
            return cls()
        with index_path.open("r", encoding="utf-8") as index_file:
            payload = json.load(index_file)
        return cls(records=payload.get("records", []))

    def save(self, path: str | Path) -> None:
        index_path = Path(path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("w", encoding="utf-8") as index_file:
            json.dump({"records": self.records}, index_file, indent=2)

    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        metadatas = metadatas or [{} for _ in texts]
        for doc_id, text, embedding, metadata in zip(ids, texts, embeddings, metadatas):
            self.records.append(
                {
                    "id": doc_id,
                    "text": text,
                    "embedding": embedding,
                    "metadata": metadata,
                }
            )

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchHit]:
        scored = []
        for record in self.records:
            score = _cosine_similarity(query_embedding, record.get("embedding", []))
            scored.append(
                SearchHit(
                    id=record["id"],
                    text=record["text"],
                    score=score,
                    metadata=record.get("metadata", {}),
                )
            )
        return sorted(scored, key=lambda hit: hit.score, reverse=True)[:top_k]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)

