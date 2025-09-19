from mcp.server.fastmcp import Context, FastMCP
from smithery.decorators import smithery
import asyncio
from typing import Any


@smithery.server()
def create_server():
    """Create and configure the MCP server."""
    server = FastMCP("Say Hello")
    
    @server.tool()
    def hello(name: str, ctx: Context) -> str:
        """Say hello to someone."""
        
        return f"Hello, {name}!"
    @server.tool()
    async def scrape(url: str, ctx: Context) -> str:
        """Scrape a website."""
        try:
            loop = asyncio.get_running_loop()

            def scrape_generate_text() -> str:
                # Lazy imports to avoid heavy initialization at server startup
                from playwright.sync_api import Page  # type: ignore
                from scrapling.fetchers import StealthyFetcher  # type: ignore

                def scroll_page(page: Any):
                    # Basic page actions; keep lightweight
                    page.mouse.wheel(10, 0)
                    page.mouse.move(100, 400)
                    page.mouse.up()
                    # Example artifact (optional)
                    # page.screenshot(path="example.png")

                page = StealthyFetcher.fetch(
                    url,
                    solve_cloudflare=True,
                    headless=True,
                    page_action=scroll_page,
                )
                return page.get_all_text()

            result = await loop.run_in_executor(None, scrape_generate_text)
            return result
        except Exception as e:
            return str(e)
        
    
    return server


if __name__ == "__main__":
    server = create_server()
    server.run(transport="streamable-http")