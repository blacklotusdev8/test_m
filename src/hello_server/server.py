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
                try:
                    from scrapling.fetchers import StealthyFetcher  # type: ignore
                except Exception:  # pragma: no cover
                    StealthyFetcher = None  # type: ignore

                def scroll_page(page: Any):
                    # Keep actions minimal to reduce flakiness in headless browser
                    try:
                        page.mouse.wheel(10, 0)
                        page.mouse.move(100, 400)
                        page.mouse.up()
                    except Exception:
                        pass

                errors: list[str] = []

                # 2) Try StealthyFetcher with relaxed options to avoid header generation failures
                if 'StealthyFetcher' in locals() and StealthyFetcher is not None:  # type: ignore
                    try:
                        page = StealthyFetcher.fetch(  # type: ignore
                            url,
                            headless=True,
                            solve_cloudflare=False,  # relax CF solving to avoid strict header requirements
                            page_action=scroll_page,
                        )
                        if hasattr(page, "get_all_text"):
                            return page.get_all_text()
                        if hasattr(page, "content"):
                            return page.content  # type: ignore[attr-defined]
                    except Exception as e:
                        errors.append(f"StealthyFetcher: {e}")

            result = await loop.run_in_executor(None, scrape_generate_text)
            return result
        except Exception as e:
            return str(e)
        
    
    return server


if __name__ == "__main__":
    server = create_server()
    server.run(transport="streamable-http")