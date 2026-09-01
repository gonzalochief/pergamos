import json

from pergamos.calibre_client import CalibreClient, Settings, parse_feed
from pergamos.server import index_book_content, search_book_content


FEED = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/terms/"><link rel="next" href="/opds/search?q=python&amp;start=20"/><entry><title>Practical Python</title><id>urn:calibre:42</id><dc:identifier>42</dc:identifier><author><name>Jane Doe</name></author><summary>A guide.</summary><category term="Python"/><link rel="http://opds-spec.org/acquisition" type="application/epub+zip" href="/download/42/epub"/></entry></feed>'''


def test_parse_feed_normalizes_book_and_links():
    page = parse_feed(FEED, "http://127.0.0.1:8080/opds/search?q=python")
    assert page.books[0].identifier == "42"
    assert page.books[0].authors == ["Jane Doe"]
    assert page.books[0].formats[0]["type"] == "application/epub+zip"
    assert page.books[0].formats[0]["url"] == "http://127.0.0.1:8080/download/42/epub"
    assert page.next_url.endswith("start=20")


def test_search_uses_calibre_search_terms_path(monkeypatch):
    client = CalibreClient(Settings("http://calibre.test"))
    requested = []

    def fake_feed(path):
        requested.append(path)
        return type("Page", (), {"books": [], "next_url": None})()

    monkeypatch.setattr(client, "feed", fake_feed)
    client.search("python books", limit=5, offset=10)
    assert requested == ["opds/search/python%20books?offset=10"]


def test_search_follows_opds_pagination_until_limit(monkeypatch):
    client = CalibreClient(Settings("http://calibre.test"))
    first = type("Book", (), {})()
    second = type("Book", (), {})()
    pages = {
        "opds/search/python?offset=0": type(
            "Page", (), {"books": [first], "next_url": "http://calibre.test/opds/search/python?offset=1"}
        )(),
        "http://calibre.test/opds/search/python?offset=1": type(
            "Page", (), {"books": [second], "next_url": None}
        )(),
    }
    monkeypatch.setattr(client, "feed", pages.__getitem__)

    assert client.search("python", limit=2) == [first, second]


def test_index_book_content_indexes_chunks(monkeypatch):
    class DummyIndex:
        def __init__(self, persist_dir):
            self.persist_dir = persist_dir

        def index_book(self, book_id, title, download_url, format_name):
            return ["chunk 1", "chunk 2"]

    monkeypatch.setattr("pergamos.server.BookRAGIndex", DummyIndex)
    payload = json.loads(index_book_content("42", "Practical Python", "http://calibre.test/download/42/epub", "epub"))

    assert payload["book_id"] == "42"
    assert payload["chunks"] == 2
    assert payload["indexed"] is True


def test_search_book_content_returns_matches(monkeypatch):
    class DummyIndex:
        def __init__(self, persist_dir):
            self.persist_dir = persist_dir

        def search(self, query, book_ids=None, k=5):
            return {
                "ids": [["42:0", "42:1"]],
                "documents": [["alpha", "beta"]],
                "metadatas": [[{"book_id": "42", "title": "Practical Python"}, {"book_id": "42", "title": "Practical Python"}]],
            }

    monkeypatch.setattr("pergamos.server.BookRAGIndex", DummyIndex)
    payload = json.loads(search_book_content("python", book_ids=["42"], k=2))

    assert payload["query"] == "python"
    assert payload["count"] == 2
    assert payload["matches"][0]["document"] == "alpha"