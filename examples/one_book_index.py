"""Index a single book into the local RAG store."""

from __future__ import annotations

from pergamos.rag.indexer import BookRAGIndex


def main() -> None:
    book_id = "42"
    title = "Distributed Systems"
    download_url = "http://127.0.0.1:8080/get/42/epub"

    index = BookRAGIndex(persist_dir=".pergamos_index")
    chunks = index.index_book(book_id, title, download_url, "epub")
    print(f"Indexed {len(chunks)} chunks for {title}")


if __name__ == "__main__":
    main()
