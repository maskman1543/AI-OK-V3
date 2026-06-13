"""Vector index wrappers."""

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


class ChromaVectorIndex:
    """Persistent ChromaDB index using caller-provided embeddings."""

    def __init__(
        self,
        persist_path: str | Path = "kiosk/data/chroma",
        collection_name: str = "kiosk_kb",
        reset: bool = False,
    ) -> None:
        self.persist_path = Path(persist_path)
        self.collection_name = collection_name
        self.reset = reset
        self._client = None
        self._collection = None

    @classmethod
    def load(
        cls,
        persist_path: str | Path = "kiosk/data/chroma",
        collection_name: str = "kiosk_kb",
    ) -> "ChromaVectorIndex":
        return cls(persist_path=persist_path, collection_name=collection_name)

    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not texts:
            return
        self._get_collection().add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas or [{} for _ in texts],
        )

    def save(self, path: str | Path | None = None) -> None:
        # PersistentClient writes changes as they are made.
        self.persist_path.mkdir(parents=True, exist_ok=True)

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchHit]:
        results = self._get_collection().query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )
        hits: list[SearchHit] = []
        for doc_id, text, distance, metadata in zip(
            results.get("ids", [[]])[0],
            results.get("documents", [[]])[0],
            results.get("distances", [[]])[0],
            results.get("metadatas", [[]])[0],
        ):
            hits.append(
                SearchHit(
                    id=doc_id,
                    text=text,
                    score=1.0 - float(distance),
                    metadata=metadata or {},
                )
            )
        return hits

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise RuntimeError("Install chromadb to use the Chroma vector store") from exc

        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_path))
        if self.reset:
            try:
                self._client.delete_collection(self.collection_name)
            except Exception:
                pass
            self.reset = False

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)

