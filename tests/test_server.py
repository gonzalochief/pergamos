import asyncio

from pergamos.server import mcp


def test_server_registers_expected_tools():
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "list_libraries",
        "search_books",
        "get_book_details",
        "index_book_content",
        "search_book_content",
    }