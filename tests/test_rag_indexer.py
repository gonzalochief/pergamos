from pergamos.rag.indexer import BookRAGIndex


class FakeEmbeddings:
    def encode(self, documents):
        return FakeVectors([[float(index)] for index, _ in enumerate(documents)])


class FakeVectors(list):
    def tolist(self):
        return list(self)


class FakeCollection:
    def __init__(self):
        self.records = {}

    def get(self, where):
        book_id = where["book_id"]
        ids = [key for key, value in self.records.items() if value["metadata"]["book_id"] == book_id]
        return {"ids": ids}

    def upsert(self, ids, documents, embeddings, metadatas):
        for chunk_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self.records[chunk_id] = {
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def delete(self, ids):
        for chunk_id in ids:
            self.records.pop(chunk_id, None)


def make_index(monkeypatch, text):
    index = BookRAGIndex()
    index.collection = FakeCollection()
    index._embedder = FakeEmbeddings()
    monkeypatch.setattr(index, "download_book", lambda url, destination: destination)
    monkeypatch.setattr("pergamos.rag.indexer.extract_text_from_epub", lambda path: text[0])
    monkeypatch.setattr("pergamos.rag.indexer.split_text", lambda value, chunk_size, overlap: value.split("|") if value else [])
    return index


def test_reindex_replaces_chunks_and_removes_stale_ids(monkeypatch):
    text = ["first|second"]
    index = make_index(monkeypatch, text)
    index.index_book("42", "Book", "https://example.test/book.epub", "epub")

    text[0] = "updated"
    chunks = index.index_book("42", "Updated Book", "https://example.test/book.epub", "epub")

    assert chunks == ["updated"]
    assert list(index.collection.records) == ["42:0"]
    assert index.collection.records["42:0"]["document"] == "updated"
    assert index.collection.records["42:0"]["metadata"]["title"] == "Updated Book"


def test_reindex_empty_text_removes_existing_book_chunks(monkeypatch):
    text = ["first|second"]
    index = make_index(monkeypatch, text)
    index.index_book("42", "Book", "https://example.test/book.epub", "epub")

    text[0] = ""
    chunks = index.index_book("42", "Book", "https://example.test/book.epub", "epub")

    assert chunks == []
    assert index.collection.records == {}


def test_reindex_preserves_other_books(monkeypatch):
    text = ["first"]
    index = make_index(monkeypatch, text)
    index.index_book("42", "Book 42", "https://example.test/42.epub", "epub")
    index.collection.records["77:0"] = {
        "document": "other book",
        "embedding": [0.0],
        "metadata": {"book_id": "77", "title": "Book 77"},
    }

    text[0] = "updated"
    index.index_book("42", "Book 42", "https://example.test/42.epub", "epub")

    assert set(index.collection.records) == {"42:0", "77:0"}


def test_failed_embedding_preserves_existing_chunks(monkeypatch):
    text = ["original"]
    index = make_index(monkeypatch, text)
    index.index_book("42", "Book", "https://example.test/book.epub", "epub")
    previous_record = index.collection.records["42:0"].copy()

    class FailedEmbeddings:
        def encode(self, documents):
            raise RuntimeError("embedding failed")

    index._embedder = FailedEmbeddings()
    text[0] = "replacement"

    try:
        index.index_book("42", "Book", "https://example.test/book.epub", "epub")
    except RuntimeError as error:
        assert str(error) == "embedding failed"
    else:
        raise AssertionError("expected embedding failure")

    assert index.collection.records["42:0"] == previous_record
