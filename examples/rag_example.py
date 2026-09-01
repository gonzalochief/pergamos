"""Example of a hybrid metadata + RAG workflow over a Calibre library."""

from __future__ import annotations

import json

from pergamos.server import index_book_content, search_book_content


def search_books(client, query: str, limit: int = 5):
    """This is a placeholder for the MCP call to search_books."""
    return client.search_books(query=query, limit=limit, offset=0)


def get_book_details(client, book_id: str):
    """This is a placeholder for the MCP call to get_book_details."""
    return client.get_book_details(identifier=book_id)


def main() -> None:
    # In real use this client would be the MCP client you configure in Claude Desktop or another app.
    # This example is intentionally simple and shows the orchestration pattern.
    sample_book = {
        "id": "42",
        "title": "Distributed Systems",
        "formats": [
            {"format": "epub", "url": "http://127.0.0.1:8080/get/42/epub"},
        ],
    }

    print("Step 1: metadata discovery")
    print(json.dumps({"query": "distributed systems", "limit": 5, "candidate": sample_book}, ensure_ascii=False))

    print("\nStep 2: book details and format selection")
    print(json.dumps(sample_book, ensure_ascii=False))

    print("\nStep 3: index the book text")
    result = index_book_content(
        book_id=sample_book["id"],
        title=sample_book["title"],
        download_url=sample_book["formats"][0]["url"],
        format_name=sample_book["formats"][0]["format"],
    )
    print(result)

    print("\nStep 4: semantic content search")
    query_result = search_book_content(
        query="What does the book say about consensus?",
        book_ids=[sample_book["id"]],
        k=5,
    )
    print(query_result)


if __name__ == "__main__":
    main()
