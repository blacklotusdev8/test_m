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
                from scrapling.fetchers import Fetcher  # type: ignore
                try:
                    from scrapling.fetchers import DynamicFetcher  # type: ignore
                except Exception:  # pragma: no cover
                    DynamicFetcher = None  # type: ignore
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

                # 1) Try DynamicFetcher first (avoids strict stealth header generation)
                if 'DynamicFetcher' in locals() and DynamicFetcher is not None:  # type: ignore
                    try:
                        page = DynamicFetcher.fetch(  # type: ignore
                            url,
                            headless=True,
                            page_action=scroll_page,
                        )
                        if hasattr(page, "get_all_text"):
                            return page.get_all_text()
                        if hasattr(page, "content"):
                            return page.content  # type: ignore[attr-defined]
                    except Exception as e:
                        errors.append(f"DynamicFetcher: {e}")

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

                # 3) Direct Playwright fallback (avoid Scrapling header generation paths)
               

                # 4) Final fallback to basic Fetcher (static HTTP)
                try:
                    resp = Fetcher.fetch(url)
                    if hasattr(resp, "get_all_text"):
                        return resp.get_all_text()
                    if hasattr(resp, "text"):
                        return resp.text  # type: ignore[attr-defined]
                    if hasattr(resp, "content"):
                        return resp.content  # type: ignore[attr-defined]
                    return str(resp)
                except Exception as e:
                    errors.append(f"Fetcher: {e}")
                    return "All fetchers failed: " + " | ".join(errors)

            result = await loop.run_in_executor(None, scrape_generate_text)
            return result
        except Exception as e:
            return str(e)
        
    
    return server


if __name__ == "__main__":
    server = create_server()
    server.run(transport="streamable-http")