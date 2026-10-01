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


@mcp.tool()
def list_all_books(limit: int = 100, offset: int = 0) -> str:
    """List all books in the library by title, useful for later research and indexing work."""
    if not 1 <= limit <= 1000 or offset < 0:
        return json.dumps({"error": "limit must be 1-1000 and offset must be non-negative"})
    try:
        books = _client().list_all_books(limit=limit, offset=offset)
        return json.dumps({"count": len(books), "books": [book.as_dict() for book in books]}, ensure_ascii=False)
    except (ConfigurationError, CalibreError) as error:
        return json.dumps({"error": str(error)})


def _rag_index() -> BookRAGIndex:
    return BookRAGIndex(persist_dir=os.environ.get("PERGAMOS_RAG_DIR", ".pergamos_index"))


def _search_matches(response: dict) -> list[dict[str, object]]:
    ids = response.get("ids", [])
    documents = response.get("documents", [])
    metadatas = response.get("metadatas", [])
    matches: list[dict[str, object]] = []
    for index, doc_list in enumerate(documents):
        for doc_index, document in enumerate(doc_list):
            metadata = (metadatas[index][doc_index] if index < len(metadatas) and doc_index < len(metadatas[index]) else {})
            if not isinstance(metadata, dict):
                metadata = {}
            title = str(metadata.get("title") or "Unknown title")
            format_name = str(metadata.get("format") or "unknown")
            chunk_index = metadata.get("chunk_index")
            source = f"{title} ({format_name}, chunk {chunk_index})" if chunk_index is not None else f"{title} ({format_name})"
            metadata = {**metadata, "title": title, "format": format_name, "source": source}
            matches.append({
                "id": ids[index][doc_index] if index < len(ids) and doc_index < len(ids[index]) else None,
                "document": document,
                "metadata": metadata,
            })
    return matches


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
        matches = _search_matches(response)
        return json.dumps({"query": query.strip(), "count": len(matches), "matches": matches}, ensure_ascii=False)
    except Exception as error:  # pragma: no cover - exercised at runtime if optional deps are missing
        return json.dumps({"error": str(error)}, ensure_ascii=False)


@mcp.tool()
def list_indexed_books() -> str:
    """List the books currently indexed in the local vector store, along with chunk counts."""
    try:
        books = _rag_index().list_books()
        return json.dumps({"count": len(books), "books": books}, ensure_ascii=False)
    except Exception as error:  # pragma: no cover - exercised when the optional index dependencies are missing
        return json.dumps({"error": str(error)}, ensure_ascii=False)


@mcp.tool()
def delete_book_index(book_id: str) -> str:
    """Remove all indexed chunks associated with a single Calibre book ID."""
    if not book_id.strip():
        return json.dumps({"error": "book_id must not be empty"})
    try:
        deleted = _rag_index().delete_book(book_id.strip())
        return json.dumps({"book_id": book_id.strip(), "deleted_chunks": deleted}, ensure_ascii=False)
    except Exception as error:  # pragma: no cover - exercised when the optional index dependencies are missing
        return json.dumps({"error": str(error), "deleted_chunks": 0}, ensure_ascii=False)


@mcp.tool()
def refresh_book_index(book_id: str, title: str, download_url: str, format_name: str) -> str:
    """Delete stale chunks for a book and reindex the current file so the local content store stays fresh."""
    if not book_id.strip():
        return json.dumps({"error": "book_id must not be empty"})
    if not title.strip():
        return json.dumps({"error": "title must not be empty"})
    if not download_url.strip():
        return json.dumps({"error": "download_url must not be empty"})
    if not format_name.strip():
        return json.dumps({"error": "format_name must not be empty"})
    try:
        chunks = _rag_index().refresh_book(book_id.strip(), title.strip(), download_url.strip(), format_name.strip())
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
def rag_search_library(query: str, limit: int = 10, offset: int = 0, k: int = 5) -> str:
    """Run a metadata search and, when available, a semantic search over the indexed content in a single call."""
    if not query.strip():
        return json.dumps({"error": "query must not be empty"})
    if not 1 <= limit <= 100 or offset < 0:
        return json.dumps({"error": "limit must be 1-100 and offset must be non-negative"})
    if k <= 0:
        return json.dumps({"error": "k must be positive"})
    try:
        books = _client().search(query.strip(), limit, offset)
    except (ConfigurationError, CalibreError) as error:
        return json.dumps({"error": str(error)})

    metadata = [book.as_dict() for book in books]
    content_matches: list[dict[str, object]] = []
    candidate_ids = [str(book.identifier).strip() for book in books if str(book.identifier).strip()]
    if candidate_ids:
        try:
            response = _rag_index().search(query.strip(), book_ids=candidate_ids, k=k)
            content_matches = _search_matches(response)
        except Exception:  # pragma: no cover - exercised at runtime if the optional index is absent
            content_matches = []

    return json.dumps(
        {
            "query": query.strip(),
            "count": len(metadata),
            "metadata": metadata,
            "content_count": len(content_matches),
            "content": content_matches,
        },
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()