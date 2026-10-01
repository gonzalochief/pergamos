import asyncio
import json

from pergamos.server import mcp


def test_server_registers_expected_tools():
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "list_libraries",
        "search_books",
        "get_book_details",
        "index_book_content",
        "search_book_content",
        "rag_search_library",
        "list_indexed_books",
        "delete_book_index",
        "refresh_book_index",
    }


def test_rag_search_library_combines_metadata_and_content(monkeypatch):
    class DummyBook:
        identifier = "42"
        title = "Distributed Systems"
        authors = ["Alice"]
        summary = "Summary"
        publisher = None
        published = None
        language = None
        tags = ["distributed"]
        formats = [{"format": "epub", "url": "https://example.test/book.epub"}]
        links = []

        def as_dict(self):
            return {
                "id": self.identifier,
                "title": self.title,
                "authors": self.authors,
                "summary": self.summary,
                "publisher": self.publisher,
                "published": self.published,
                "language": self.language,
                "tags": self.tags,
                "formats": self.formats,
                "links": self.links,
            }

    monkeypatch.setattr("pergamos.server._client", lambda: type("Client", (), {"search": lambda self, query, limit, offset: [DummyBook()]})())
    monkeypatch.setattr(
        "pergamos.server._rag_index",
        lambda: type("Index", (), {"search": lambda self, query, book_ids=None, k=5: {"ids": [["42:0"]], "documents": [["consensus is important"]], "metadatas": [[{"book_id": "42", "title": "Distributed Systems", "chunk_index": 0}]]}})(),
    )

    result = asyncio.run(mcp.call_tool("rag_search_library", {"query": "consensus", "limit": 5, "k": 2}))
    payload = json.loads(result.content[0].text)

    assert payload["query"] == "consensus"
    assert payload["metadata"][0]["id"] == "42"
    assert payload["content"][0]["id"] == "42:0"
    assert payload["content"][0]["document"] == "consensus is important"


def test_index_management_tools(monkeypatch):
    class FakeIndex:
        def list_books(self):
            return [{"book_id": "42", "title": "Distributed Systems", "formats": ["epub"], "chunk_count": 3}]

        def delete_book(self, book_id):
            assert book_id == "42"
            return 3

    monkeypatch.setattr("pergamos.server._rag_index", lambda: FakeIndex())

    indexed = asyncio.run(mcp.call_tool("list_indexed_books", {}))
    assert json.loads(indexed.content[0].text)["books"][0]["book_id"] == "42"

    deleted = asyncio.run(mcp.call_tool("delete_book_index", {"book_id": "42"}))
    assert json.loads(deleted.content[0].text)["deleted_chunks"] == 3


def test_search_book_content_includes_citation_metadata(monkeypatch):
    monkeypatch.setattr(
        "pergamos.server._rag_index",
        lambda: type(
            "Index",
            (),
            {"search": lambda self, query, book_ids=None, k=5: {"ids": [["42:0"]], "documents": [["consensus is important"]], "metadatas": [[{"book_id": "42", "title": "Distributed Systems", "format": "epub", "chunk_index": 0}]]}},
        )(),
    )

    result = asyncio.run(mcp.call_tool("search_book_content", {"query": "consensus", "book_ids": ["42"], "k": 2}))
    payload = json.loads(result.content[0].text)

    assert payload["matches"][0]["metadata"]["title"] == "Distributed Systems"
    assert payload["matches"][0]["metadata"]["source"] == "Distributed Systems (epub, chunk 0)"


def test_refresh_book_index_tool(monkeypatch):
    class FakeIndex:
        def refresh_book(self, *args, **kwargs):
            return ["refreshed"]

    monkeypatch.setattr("pergamos.server._rag_index", lambda: FakeIndex())

    refreshed = asyncio.run(mcp.call_tool("refresh_book_index", {"book_id": "42", "title": "Book", "download_url": "https://example.test/book.epub", "format_name": "epub"}))
    payload = json.loads(refreshed.content[0].text)

    assert payload["indexed"] is True
    assert payload["chunks"] == 1