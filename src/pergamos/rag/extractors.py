"""Text extraction and chunking utilities for indexed books."""

from __future__ import annotations

from typing import Iterable


def split_text(text: str, chunk_size: int = 700, overlap: int = 80) -> list[str]:
    """Split text into overlapping chunks while preserving readable boundaries."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunk = cleaned[start:end]
        chunks.append(chunk)
        if end == len(cleaned):
            break
        start = max(start + chunk_size - overlap, end - overlap)
    return chunks


def _iter_epub_texts(book) -> Iterable[str]:
    import ebooklib
    from ebooklib import epub

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_content()
            if not content:
                continue
            try:
                text = content.decode("utf-8", errors="ignore")
            except Exception:
                text = str(content)
            if text:
                yield text


def extract_text_from_epub(path: str) -> str:
    """Extract readable text from an EPUB file."""
    try:
        from ebooklib import epub
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when optional dep is missing
        raise RuntimeError("Install pergamos[rag] to enable EPUB extraction") from exc

    book = epub.read_epub(path)
    return "\n".join(_iter_epub_texts(book))


def extract_text_from_pdf(path: str) -> str:
    """Extract readable text from a PDF file."""
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when optional dep is missing
        raise RuntimeError("Install pergamos[rag] to enable PDF extraction") from exc

    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text:
            pages.append(page_text)
    return "\n\n".join(pages)
