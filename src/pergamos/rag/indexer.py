"""Index Calibre book content into a local vector store."""

from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.request import urlopen

from .extractors import extract_text_from_epub, extract_text_from_pdf, split_text


class BookRAGIndex:
    """Minimal RAG indexer for a Calibre book library.

    The metadata server remains the discovery layer. This class is intentionally focused on
    full-text indexing for selected book IDs and format URLs.
    """

    def __init__(self, persist_dir: str = ".pergamos_index", model_name: str = "all-MiniLM-L6-v2"):
        self.persist_dir = persist_dir
        self.model_name = model_name
        self.collection = None
        self._embedder = None

    def _ensure_dependencies(self) -> None:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when optional deps are missing
            raise RuntimeError("Install pergamos[rag] before using BookRAGIndex") from exc

        self._embedder = SentenceTransformer(self.model_name)
        client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = client.get_or_create_collection(
            name="pergamos_books",
            metadata={"hnsw:space": "cosine"},
        )

    def download_book(self, url: str, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url) as response:
            target.write_bytes(response.read())
        return target

    def index_book(self, book_id: str, title: str, download_url: str, format_name: str) -> list[str]:
        """Download a book, extract text, split it into chunks, and store embeddings."""
        if self.collection is None or self._embedder is None:
            self._ensure_dependencies()

        normalized = format_name.lower()
        if normalized not in {"epub", "pdf"}:
            raise ValueError(f"Unsupported book format for indexing: {format_name}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / f"{book_id}.{normalized}"
            self.download_book(download_url, tmp_path)

            if normalized == "epub":
                text = extract_text_from_epub(str(tmp_path))
            else:
                text = extract_text_from_pdf(str(tmp_path))

        chunks = split_text(text, chunk_size=700, overlap=80)
        if not chunks:
            return []

        ids = [f"{book_id}:{index}" for index in range(len(chunks))]
        documents = chunks
        metadatas = [
            {
                "book_id": str(book_id),
                "title": title,
                "format": format_name,
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ]
        embeddings = self._embedder.encode(documents).tolist()

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return chunks

    def search(self, query: str, book_ids: list[str] | None = None, k: int = 5):
        if self.collection is None or self._embedder is None:
            self._ensure_dependencies()

        where = {"book_id": {"$in": book_ids}} if book_ids else None
        return self.collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
        )
