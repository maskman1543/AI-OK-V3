"""Offline KB builder: documents -> chunks -> embeddings -> index."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from kiosk.rag.embedder import SentenceTransformerEmbedder
from kiosk.rag.index import ChromaVectorIndex, VectorIndex

DOCLING_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".md",
    ".adoc",
    ".asciidoc",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp",
    ".wav",
    ".mp3",
    ".vtt",
}
TEXT_SUFFIXES = {".txt"}
SUPPORTED_SUFFIXES = DOCLING_SUFFIXES | TEXT_SUFFIXES


def ingest_paths(
    input_paths: Iterable[str | Path],
    index_path: str | Path = "kiosk/data/chroma",
    embedding_model: str | None = None,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
    store: str = "chroma",
    collection_name: str = "kiosk_kb",
    converted_text_dir: str | Path | None = "kiosk/data/converted_text",
) -> int:
    """Build or replace the local vector index."""

    chunks: list[str] = []
    metadatas: list[dict[str, str | int]] = []
    reader = DocumentReader()
    for path in _iter_input_files(input_paths):
        text = reader.read(path)
        if converted_text_dir is not None:
            _write_converted_text(path, text, converted_text_dir)
        for chunk_number, chunk in enumerate(_chunk_text(text, chunk_size, chunk_overlap)):
            chunks.append(chunk)
            metadatas.append(
                {
                    "source": str(path),
                    "chunk": chunk_number,
                    "reader": reader.last_reader,
                }
            )

    embedder = SentenceTransformerEmbedder(embedding_model)
    embeddings = embedder.embed(chunks)
    ids = [f"chunk-{idx}" for idx in range(len(chunks))]

    if store == "chroma":
        index = ChromaVectorIndex(index_path, collection_name=collection_name, reset=True)
    elif store == "json":
        index = VectorIndex()
    else:
        raise ValueError(f"Unsupported vector store: {store}")
    index.add(ids, chunks, embeddings, metadatas)
    index.save(index_path)
    return len(chunks)


class DocumentReader:
    """Converts supported knowledge files to plain text for chunking."""

    def __init__(self) -> None:
        self._converter = None
        self.last_reader = ""

    def read(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            self.last_reader = "text"
            return path.read_text(encoding="utf-8")

        if suffix in DOCLING_SUFFIXES:
            self.last_reader = "docling"
            return self._read_with_docling(path)

        raise ValueError(f"Unsupported document type: {path}")

    def _read_with_docling(self, path: Path) -> str:
        converter = self._load_docling_converter()
        result = converter.convert(path)
        return result.document.export_to_markdown()

    def _load_docling_converter(self):
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter
            except ImportError as exc:  # pragma: no cover - depends on deployment
                raise RuntimeError("Install docling to ingest rich document files") from exc
            self._converter = DocumentConverter()
        return self._converter


def _iter_input_files(input_paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for input_path in input_paths:
        path = Path(input_path)
        if path.is_dir():
            files.extend(
                sorted(
                    child
                    for child in path.rglob("*")
                    if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES
                )
            )
            continue

        if not path.exists():
            raise FileNotFoundError(f"Missing input document: {path}")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported document type: {path}")
        files.append(path)

    return files


def _read_document(path: Path) -> str:
    """Backward-compatible wrapper for callers that used the old helper."""

    return DocumentReader().read(path)


def _read_pdf_with_pypdf(path: Path) -> str:
    """Legacy PDF reader kept for deployments that intentionally avoid Docling."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on deployment
        raise RuntimeError("Install pypdf to ingest PDF files without Docling") from exc
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_document_legacy(path: Path) -> str:
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


def _write_converted_text(source_path: Path, text: str, output_dir: str | Path) -> Path:
    output_path = Path(output_dir) / f"{source_path.stem}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path


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
    parser.add_argument("inputs", nargs="+", help="Files or folders to ingest with Docling")
    parser.add_argument("--index-path", default="kiosk/data/chroma")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--store", choices=["chroma", "json"], default="chroma")
    parser.add_argument("--collection-name", default="kiosk_kb")
    parser.add_argument("--converted-text-dir", default="kiosk/data/converted_text")
    args = parser.parse_args()

    count = ingest_paths(
        args.inputs,
        index_path=args.index_path,
        embedding_model=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        store=args.store,
        collection_name=args.collection_name,
        converted_text_dir=args.converted_text_dir,
    )
    print(f"Ingested {count} chunks into {args.store} at {args.index_path}")


if __name__ == "__main__":
    main()

