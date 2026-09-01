"""Optional RAG helpers for indexing Calibre book content."""

from .extractors import split_text
from .indexer import BookRAGIndex
from .search import semantic_search

__all__ = ["BookRAGIndex", "semantic_search", "split_text"]
