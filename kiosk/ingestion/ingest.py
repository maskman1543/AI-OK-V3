"""Offline KB builder: documents -> chunks -> embeddings -> index."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from kiosk.rag.embedder import SentenceTransformerEmbedder
from kiosk.rag.index import VectorIndex


def ingest_paths(
    input_paths: Iterable[str | Path],
    index_path: str | Path = "kiosk/data/index.json",
    embedding_model: str | None = None,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> int:
    """Build or replace the local JSON vector index."""

    chunks: list[str] = []
    metadatas: list[dict[str, str | int]] = []
    for input_path in input_paths:
        path = Path(input_path)
        text = _read_document(path)
        for chunk_number, chunk in enumerate(_chunk_text(text, chunk_size, chunk_overlap)):
            chunks.append(chunk)
            metadatas.append({"source": str(path), "chunk": chunk_number})

    embedder = SentenceTransformerEmbedder(embedding_model)
    embeddings = embedder.embed(chunks)
    ids = [f"chunk-{idx}" for idx in range(len(chunks))]

    index = VectorIndex()
    index.add(ids, chunks, embeddings, metadatas)
    index.save(index_path)
    return len(chunks)


def _read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise RuntimeError("Install pypdf to ingest PDF files") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")

    raise ValueError(f"Unsupported document type: {path}")


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the kiosk RAG index")
    parser.add_argument("inputs", nargs="+", help="PDF, TXT, or Markdown files to ingest")
    parser.add_argument("--index-path", default="kiosk/data/index.json")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    args = parser.parse_args()

    count = ingest_paths(
        args.inputs,
        index_path=args.index_path,
        embedding_model=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Ingested {count} chunks into {args.index_path}")


if __name__ == "__main__":
    main()

