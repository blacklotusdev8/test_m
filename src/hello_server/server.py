from mcp.server.fastmcp import Context, FastMCP
from scrapling.fetchers import StealthyFetcher 
from playwright.sync_api import Page
from smithery.decorators import smithery
import asyncio


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

            def scroll_page(page: Page):
                page.mouse.wheel(10, 0)
                page.mouse.move(100, 400)
                page.mouse.up()
                page.screenshot(path="example.png")
                
            def scrape_generate_image():
                page =  StealthyFetcher.fetch(
                url,solve_cloudflare=True,headless=True,
                page_action=scroll_page
                    )
                
                return page.get_all_text()

            result = await loop.run_in_executor(None, scrape_generate_image)
            return result
        except Exception as e:
            return str(e)
        return page.content    

    return server
