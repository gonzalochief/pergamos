# Pergamos

![Tests](https://github.com/gonzalochief/pergamos/actions/workflows/test.yml/badge.svg)

Pergamos is a read-only MCP server that lets Claude Desktop search and inspect a Calibre library through the Calibre Content Server.

## Requirements

- macOS with Python 3.10 or newer
- Calibre with the Content Server running
- The official MCP Python SDK, installed by the project setup below

Start the Calibre Content Server from **Connect/share > Start Content server**. The default address is `http://127.0.0.1:8080`.

## Install

```sh
cd /path/to/pergamos
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Configure Claude Desktop

Add a server entry to Claude Desktop's configuration file, usually `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pergamos-calibre": {
      "command": "/path/to/pergamos/.venv/bin/pergamos",
      "env": {
        "CALIBRE_SERVER_URL": "http://127.0.0.1:8080"
      }
    }
  }
}
```

For a Content Server with authentication, add `CALIBRE_USERNAME` and `CALIBRE_PASSWORD` to the same `env` object. `CALIBRE_REQUEST_TIMEOUT` may be set to a positive number of seconds. A URL prefix such as `http://127.0.0.1:8080/calibre` is supported.

Restart Claude Desktop after changing its configuration.

For the optional RAG tools, add the `PERGAMOS_RAG_DIR` environment variable if you want the vector store to live somewhere other than the default `.pergamos_index` directory:

```json
{
  "mcpServers": {
    "pergamos-calibre": {
      "command": "/path/to/pergamos/.venv/bin/pergamos",
      "env": {
        "CALIBRE_SERVER_URL": "http://127.0.0.1:8080",
        "PERGAMOS_RAG_DIR": "/path/to/pergamos/.pergamos_index"
      }
    }
  }
}
```

**Note:** Make sure that the .pergamos_index is created inside the mcp directory.
```mkdir -p /path/to/pergamos/.pergamos_index```

## Tools

- `list_libraries`: checks the server and returns the root OPDS feed.
- `search_books`: performs a Calibre library-wide search across the metadata fields indexed by Calibre, including titles, authors, tags, comments, and identifiers. It accepts `query`, `limit` (1-100), and `offset`, and follows OPDS pagination up to the requested limit.
- `list_all_books`: returns all books in the library by title and metadata without a search query, which is useful for research planning and later indexing work.
- `get_book_details`: returns metadata and available format links for a Calibre book identifier.
- `index_book_content`: downloads a selected book file, extracts the text, splits it into chunks, and stores the embeddings for semantic retrieval.
- `search_book_content`: searches the indexed text chunks for one or more book IDs using a semantic query.
- `list_indexed_books`: returns the books currently present in the local vector store, including title, format, and chunk counts.
- `delete_book_index`: removes all indexed chunks for a single Calibre book ID, useful for re-indexing or cleanup.
- `refresh_book_index`: deletes stale chunks for a book and reindexes the current file so the content store stays fresh without a full rebuild.
- `rag_search_library`: runs the metadata search and content search in one call, returning both the book hits and any matching indexed chunks.

The server does not change the library or download files. Format URLs are returned as metadata so Claude can identify available editions.

Calibre's Content Server search is metadata search. It does not search the full body text of EPUB, PDF, or other book files.

## Example workflow

This is the recommended pattern for doing RAG with a Calibre library:

```python
# 1) Discover likely books by metadata
search = {
    "query": "distributed systems",
    "limit": 5,
    "offset": 0,
}

# 2) Inspect the chosen book and pick the format to index
book = {
    "id": "42",
    "title": "Distributed Systems",
    "formats": [
        {"format": "epub", "url": "http://127.0.0.1:8080/get/42/epub"},
    ],
}

# 3) Index the full text of the selected book
index_book_content(
    book_id="42",
    title="Distributed Systems",
    download_url="http://127.0.0.1:8080/get/42/epub",
    format_name="epub",
)

# 4) Run semantic search over the indexed text for that book
search_book_content(
    query="What does the book say about consensus?",
    book_ids=["42"],
    k=5,
)
```

In practice, Claude Desktop can call the tools in that order:

1. `search_books` to find candidate books
2. `get_book_details` to fetch the exact metadata and format URLs
3. `index_book_content` to add the book contents to the RAG index
4. `search_book_content` to answer question-style queries over the indexed text

This gives you metadata retrieval plus semantic content retrieval without replacing the Calibre search layer.

If you want to enumerate the library before choosing which books to index, use `list_all_books`:

```python
list_all_books(limit=100, offset=0)
```

This is especially helpful for research planning, book-by-book indexing, or preparing a corpus of books for deeper semantic work.

A single hybrid call is also available:

```python
rag_search_library(
    query="What does the book say about consensus?",
    limit=5,
    k=3,
)
```

This returns the metadata hits from Calibre and any matching semantic snippets from the indexed content for those books.

The semantic matches include citation-style metadata such as the book title, format, chunk index, and a `source` string that is suitable for agent responses.

When you need to maintain the local index, you can inspect or prune it without touching the library itself:

```python
list_indexed_books()
delete_book_index("42")
refresh_book_index(
    book_id="42",
    title="Distributed Systems",
    download_url="http://127.0.0.1:8080/get/42/epub",
    format_name="epub",
)
```

This is useful for re-indexing a book after a format change, cleaning stale chunks, or keeping the local vector store in sync with the current library.

## Dual-layer RAG pattern

For true RAG, keep Pergamos as the metadata/discovery layer and add a separate content indexer for the actual book files. The metadata server should answer questions like "which books match this topic?" while the content layer downloads the selected EPUB/PDF, extracts the text, chunks it, embeds it, and stores the vectors for semantic search.

A minimal starter implementation is included under `src/pergamos/rag/`:

- `extractors.py` handles text extraction and chunking
- `indexer.py` downloads a book, extracts text, and indexes embeddings
- `search.py` exposes a simple semantic search wrapper

Install the optional RAG extras with:

```sh
python3 -m pip install -e '.[rag]'
```

This keeps the library browsing layer read-only while enabling a full-text retrieval pipeline on top of the same book metadata.

## Runnable examples

The repo includes a few ready-to-run examples under `examples/`:

- `examples/rag_example.py`: full orchestration example using the metadata + content tools in sequence.
- `examples/one_book_index.py`: indexes a single book into the local vector store.

Run them with:

```sh
.venv/bin/python examples/rag_example.py
.venv/bin/python examples/one_book_index.py
```

## Docker Compose

A minimal stack can be started with Docker Compose for local development:

```sh
docker compose up --build
```

This starts:

- `pergamos`: the MCP server
- `calibre`: the Calibre web content server

The stack uses a named volume for the local vector index and binds the Calibre content server to port `8080`.

You can customize the runtime variables by copying the example environment file:

```sh
cp .env.example .env
```

Then edit `.env` with your local Calibre URL and credentials. The Compose file can also be pointed at `http://calibre:8080` if you want the containerized service name instead of a host-bound URL.

## Common commands

Use the included Makefile for the main project tasks:

```sh
make install
make test
make run
make docker-up
make docker-down
```

## Manual run

Claude Desktop communicates with the server over stdio. To run it directly for diagnostics:

```sh
CALIBRE_SERVER_URL=http://127.0.0.1:8080 .venv/bin/pergamos
```

Do not print diagnostic messages to stdout because stdout is reserved for MCP protocol traffic.

## Security

Prefer a local Calibre server bound to `127.0.0.1`. If the server is reachable over a network, enable Calibre authentication and HTTPS. Keep credentials in Claude Desktop's environment configuration and do not commit that file.

## Security checklist for commits

Before creating an initial commit or submitting a PR, confirm that:

- `.env`, `.env.local`, and any credential file are excluded from git
- generated data such as `.pergamos_index/` and local caches are ignored
- documentation uses neutral examples like `/path/to/pergamos` instead of machine-specific paths
- real Calibre URLs, usernames, and passwords are never hard-coded into the repository
- example config files are safe placeholders, not live local configuration

A quick review command is:

```sh
git status --short
git ls-files .env .pergamos_index .venv .pytest_cache
```

## Development

```sh
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```
