"""Convenience wrapper for vector-based semantic queries."""

from __future__ import annotations

from .indexer import BookRAGIndex


def semantic_search(query: str, book_ids: list[str] | None = None, k: int = 5, persist_dir: str = ".pergamos_index"):
    """Search the indexed content for relevant passages."""
    index = BookRAGIndex(persist_dir=persist_dir)
    return index.search(query=query, book_ids=book_ids, k=k)
