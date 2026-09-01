# Pergamos development notes

This is a standard-Python MCP server using the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and stdio transport. Calibre integration uses the Content Server's OPDS/HTTP interface documented at https://manual.calibre-ebook.com/server.html.

Keep MCP protocol traffic on stdout. Send diagnostics to stderr only. Keep the server read-only unless the tool contract and tests are updated explicitly.