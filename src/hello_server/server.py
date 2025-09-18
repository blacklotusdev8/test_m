from mcp.server.fastmcp import Context, FastMCP
from scrapling.fetchers import StealthyFetcher 
from playwright.sync_api import Page
from smithery.decorators import smithery

@smithery.server()
def create_server():
    """Create and configure the MCP server."""
    server = FastMCP("Say Hello")

    @server.tool()
    def hello(name: str, ctx: Context) -> str:
        """Say hello to someone."""
        session_config = ctx.session_config
        if session_config.pirate_mode:
            return f"Ahoy, {name}!"
        else:
            return f"Hello, {name}!"
    @server.tool()
    def scrape(url: str, ctx: Context) -> str:
        """Scrape a website."""
        try:
            def scroll_page(page: Page):
                page.mouse.wheel(10, 0)
                page.mouse.move(100, 400)
                page.mouse.up()

            page = StealthyFetcher.fetch(
                url,
                page_action=scroll_page
            )
        except Exception as e:
            return str(e)
        return page.content    

    return server
