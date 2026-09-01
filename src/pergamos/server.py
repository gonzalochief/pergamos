"""MCP stdio server exposing read-only Calibre tools and optional book-content RAG tools."""

from __future__ import annotations

import json
import os

from mcp.server.mcpserver import MCPServer

from .calibre_client import CalibreClient, CalibreError
from .config import ConfigurationError, Settings
from .rag.indexer import BookRAGIndex

mcp = MCPServer("Pergamos Calibre")


def _client() -> CalibreClient:
    return CalibreClient(Settings.from_environment())


@mcp.tool()
def list_libraries() -> str:
    """List the libraries exposed by the configured Calibre Content Server."""
    try:
        page = _client().list_libraries()
        return json.dumps({"libraries": [book.as_dict() for book in page.books]}, ensure_ascii=False)
    except (ConfigurationError, CalibreError) as error:
        return json.dumps({"error": str(error)})


@mcp.tool()
def search_books(query: str, limit: int = 20, offset: int = 0) -> str:
    """Search Calibre books by full text and return metadata plus available formats."""
    if not query.strip():
        return json.dumps({"error": "query must not be empty"})
    if not 1 <= limit <= 100 or offset < 0:
        return json.dumps({"error": "limit must be 1-100 and offset must be non-negative"})
    try:
        books = _client().search(query.strip(), limit, offset)
        return json.dumps({"query": query, "count": len(books), "books": [book.as_dict() for book in books]}, ensure_ascii=False)
    except (ConfigurationError, CalibreError) as error:
        return json.dumps({"error": str(error)})


@mcp.tool()
def get_book_details(identifier: str) -> str:
    """Return detailed metadata and available format links for one Calibre book."""
    if not identifier.strip():
        return json.dumps({"error": "identifier must not be empty"})
    try:
        return json.dumps(_client().get_book(identifier.strip()).as_dict(), ensure_ascii=False)
    except (ConfigurationError, CalibreError) as error:
        return json.dumps({"error": str(error)})


def _rag_index() -> BookRAGIndex:
    return BookRAGIndex(persist_dir=os.environ.get("PERGAMOS_RAG_DIR", ".pergamos_index"))


@mcp.tool()
def index_book_content(book_id: str, title: str, download_url: str, format_name: str) -> str:
    """Download a book file, extract text, split it into chunks, and index the content for semantic search."""
    if not book_id.strip():
        return json.dumps({"error": "book_id must not be empty"})
    if not title.strip():
        return json.dumps({"error": "title must not be empty"})
    if not download_url.strip():
        return json.dumps({"error": "download_url must not be empty"})
    if not format_name.strip():
        return json.dumps({"error": "format_name must not be empty"})
    try:
        chunks = _rag_index().index_book(book_id.strip(), title.strip(), download_url.strip(), format_name.strip())
        return json.dumps(
            {
                "book_id": book_id.strip(),
                "title": title.strip(),
                "format": format_name.strip(),
                "chunks": len(chunks),
                "indexed": True,
            },
            ensure_ascii=False,
        )
    except Exception as error:  # pragma: no cover - exercised at runtime if optional deps are missing
        return json.dumps({"error": str(error), "indexed": False}, ensure_ascii=False)


@mcp.tool()
def search_book_content(query: str, book_ids: list[str] | None = None, k: int = 5) -> str:
    """Search the indexed text for relevant chunks within one or more Calibre books."""
    if not query.strip():
        return json.dumps({"error": "query must not be empty"})
    if k <= 0:
        return json.dumps({"error": "k must be positive"})
    try:
        response = _rag_index().search(query.strip(), book_ids=book_ids, k=k)
        ids = response.get("ids", [])
        documents = response.get("documents", [])
        metadatas = response.get("metadatas", [])
        matches = []
        for index, doc_list in enumerate(documents):
            for doc_index, document in enumerate(doc_list):
                metadata = (metadatas[index][doc_index] if index < len(metadatas) and doc_index < len(metadatas[index]) else {})
                matches.append({
                    "id": ids[index][doc_index] if index < len(ids) and doc_index < len(ids[index]) else None,
                    "document": document,
                    "metadata": metadata,
                })
        return json.dumps({"query": query.strip(), "count": len(matches), "matches": matches}, ensure_ascii=False)
    except Exception as error:  # pragma: no cover - exercised at runtime if optional deps are missing
        return json.dumps({"error": str(error)}, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()