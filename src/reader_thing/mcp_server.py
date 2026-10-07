"""An MCP endpoint so agents can push Markdown to read later."""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .pipeline import save_markdown


def create_mcp(conn, storage):
    """Returns (server, ASGI app serving it at /mcp)."""
    server = MCPServer(
        "reader-thing",
        instructions=(
            "A read-it-later queue. Save Markdown here and it becomes an EPUB "
            "the user reads on their e-reader."
        ),
    )

    @server.tool()
    def save_for_later(
        markdown: str, title: str | None = None, source_url: str | None = None
    ) -> dict:
        """Save a Markdown document to the user's reading list.

        It's converted to an EPUB for an e-reader, so write it to be read
        start to finish. Tables, fenced code, and footnotes are supported;
        images must be absolute URLs (or relative to `source_url`).

        Args:
            markdown: The document. A leading `# Heading` is used as the title
                if `title` isn't given.
            title: The title shown in the reading list.
            source_url: Where the content came from, if anywhere; linked from
                the document.
        """
        row = save_markdown(conn, storage, markdown, title=title, url=source_url)
        return {"id": row["id"], "title": row["title"]}

    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        # It's behind a reverse proxy under its own hostname, and the token
        # already keeps out requests that didn't come from a configured client.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    return server, app
