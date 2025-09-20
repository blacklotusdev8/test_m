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
    
    @server.tool()
    async def ai_generate(request_type: str, user_message: str, ctx: Context) -> dict:
        """
        Interact with ai for AI model responses.
        
        Args:
            request_type: Type of request - "text", "image", or "web_search"
            user_message: The prompt or query to send
            
        Returns:
            Dictionary with content, sources, and optionally images
        """
        try:
            loop = asyncio.get_running_loop()
            
            def run_lmarena_session() -> dict:
                # Lazy imports
                import re
                from time import sleep
                from typing import Optional, Dict, List, Any
                
                try:
                    from scrapling.fetchers import StealthyFetcher  # type: ignore
                    from playwright.sync_api import Page  # type: ignore
                except ImportError as e:
                    return {"error": f"Import failed: {e}", "error_type": "ImportError"}
                
                # Selectors
                SEL_OPEN_MENU_BTN = r'button.border-border:nth-child(1)'
                SEL_SIDE_BY_SIDE_TEXT = "div.hover\:bg-surface-highlight:nth-child(2)"
                SEL_TOP_RIGHT_BUTTON = r'.max-w-full > div:nth-child(2) > div:nth-child(1) > form:nth-child(1) > div:nth-child(1) > div:nth-child(3) > div:nth-child(1) > div:nth-child(2) > button:nth-child(2)'
                SEL_INPUT = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div.flex.w-full.flex-1.flex-col.items-center.justify-center.px-4 > div > div.relative.hidden.w-full.max-w-full.sm\:block > div.bg-surface-primary.relative.flex.flex-col.rounded-\[0\.9rem\].md\:items-center.md\:gap-2 > div > form > div.flex.w-full.flex-col.justify-between.gap-1.md\:gap-2 > textarea'
                SEL_SUBMIT_BUTTON = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div.flex.w-full.flex-1.flex-col.items-center.justify-center.px-4 > div > div.relative.hidden.w-full.max-w-full.sm\:block > div.bg-surface-primary.relative.flex.flex-col.rounded-\[0\.9rem\].md\:items-center.md\:gap-2 > div > form > div.flex.w-full.flex-col.justify-between.gap-1.md\:gap-2 > div > div.flex.items-center.gap-2 > button'
                SEL_OK_BUTTON = r'button.px-4:nth-child(1)'
                SEL_ACCEPT_COOKIES_BUTTON = r'button.py-3:nth-child(2)'
                SEL_TRANSITION_OPACITY = r'div.transition-opacity'
                SEL_IMG_3 = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div > div > div.relative.overflow-hidden.-mb-4.min-h-0.flex-1 > div > div > div > div > ol > div.flex.min-w-0.flex-col.gap-2.lg\:flex-row.lg\:gap-3 > div:nth-child(3) > div.no-scrollbar.relative.flex.w-full.flex-1.flex-col.overflow-x-auto.border-border-faint.border-t > div > div.flex.w-full.flex-row.items-center.gap-2.justify-center > div > div > img'
                SEL_IMG_1 = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div > div > div.relative.overflow-hidden.-mb-4.min-h-0.flex-1 > div > div > div > div > ol > div.flex.min-w-0.flex-col.gap-2.lg\:flex-row.lg\:gap-3 > div:nth-child(1) > div.no-scrollbar.relative.flex.w-full.flex-1.flex-col.overflow-x-auto.border-border-faint.border-t > div > div.flex.w-full.flex-row.items-center.gap-2.justify-center > div > div > img'
                
                # URLs
                url = "https://lmarena.ai/?mode=direct"
                url_image = "https://lmarena.ai/?mode=side-by-side&chat-modality=image"
                url_web_search = "https://lmarena.ai/?chat-modality=search&mode=direct"
                
                # Choose URL based on request type
                target_url = url
                if request_type == "image":
                    target_url = url_image
                elif request_type in ("web_search", "search"):
                    target_url = url_web_search
                
                def clean_and_separate_text(raw_text: str, user_prompt: Optional[str] = None) -> dict:
                    """Clean text and separate sources from main content"""
                    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
                    
                    url_re = re.compile(r'https?://\S+')
                    number_re = re.compile(r'^\d+([.)])?$')
                    
                    # Noise patterns
                    navigation_items = {'lmarena', 'new chat', 'leaderboard', 'today', 'more', 'direct chat', 'login'}
                    noise_prefixes = ('gemini-', 'message from', 'search')
                    disclaimer_keywords = (
                        'inputs are processed', 'your conversations', 'do not submit',
                        'by continuing to use our services', 'may otherwise be disclosed publicly',
                        'acknowledge and direct us'
                    )
                    model_line_re = re.compile(
                        r'^(gpt|gemini|claude|llama|qwen|mixtral|mistral|deepseek|vicuna|falcon|phi|yi|cohere|command|sonnet|opus|haiku)[\w_.\-]*$',
                        re.IGNORECASE
                    )
                    
                    def normalize_text(s: str) -> str:
                        return re.sub(r'\s+', ' ', re.sub(r'[^\w\u0600-\u06FF]+', ' ', s or '')).strip().lower()
                    
                    def is_noise_line(ln: str) -> bool:
                        l = ln.strip().lower()
                        if user_prompt and normalize_text(ln) == normalize_text(user_prompt):
                            return True
                        if model_line_re.match(ln.strip()):
                            return True
                        if l in navigation_items:
                            return True
                        if any(l.startswith(p) for p in noise_prefixes):
                            return True
                        if any(k in l for k in disclaimer_keywords):
                            return True
                        return False
                    
                    # Find sources section
                    source_labels = {
                        'sources', 'source', 'references', 'refs', 'links', 'citations',
                        'المصادر', 'مصادر', 'المراجع', 'روابط', 'مراجع', 'المراجع والمصادر'
                    }
                    sources_start_idx = -1
                    for i, ln in enumerate(lines):
                        token = ln.strip(' :').lower()
                        if token in source_labels:
                            sources_start_idx = i
                            break
                    
                    sources = []
                    content_lines = []
                    
                    # Extract sources if found
                    if sources_start_idx != -1:
                        for i in range(sources_start_idx + 1, len(lines)):
                            ln = lines[i]
                            if url_re.search(ln):
                                sources.append({'url': url_re.search(ln).group(0).rstrip(').,;')})
                            elif not is_noise_line(ln) and len(ln) > 60:
                                # Start of content
                                content_lines = lines[i:]
                                break
                    else:
                        content_lines = lines
                    
                    # Clean content
                    main_content = []
                    for ln in content_lines:
                        if not is_noise_line(ln) and not url_re.search(ln) and not number_re.match(ln):
                            main_content.append(ln)
                    
                    # Remove duplicates
                    seen = set()
                    deduped = []
                    for ln in main_content:
                        if ln not in seen:
                            seen.add(ln)
                            deduped.append(ln)
                    
                    return {
                        'content': '\n'.join(deduped),
                        'sources': sources,
                        'raw_sources_text': ''
                    }
                
                def automate(page: Page):
                    """Automate interaction with lmarena.ai"""
                    try:
                        # Wait for page load
                        sleep(15)
                        
                        # Accept cookies if present
                        try:
                            page.locator(SEL_ACCEPT_COOKIES_BUTTON).click(timeout=5000)
                        except:
                            pass
                        
                        
                        # Click transition overlay if present
                        try:
                            page.wait_for_selector(SEL_TRANSITION_OPACITY, state="visible", timeout=6000)
                            element = page.locator(SEL_TRANSITION_OPACITY).first
                            box = element.bounding_box()
                            if box:
                                center_x = box["x"] + box["width"] / 2
                                center_y = box["y"] + box["height"] / 2
                                page.mouse.click(center_x, center_y)
                        except:
                            pass
                        
                        # Accept cookies if present
                        try:
                            page.locator(SEL_ACCEPT_COOKIES_BUTTON).click(timeout=5000)
                        except:
                            pass
                        
                        
                        # Click transition overlay if present
                        try:
                            page.wait_for_selector(SEL_TRANSITION_OPACITY, state="visible", timeout=6000)
                            element = page.locator(SEL_TRANSITION_OPACITY).first
                            box = element.bounding_box()
                            if box:
                                center_x = box["x"] + box["width"] / 2
                                center_y = box["y"] + box["height"] / 2
                                page.mouse.click(center_x, center_y)
                        except:
                            pass
                        try:
                            page.locator(SEL_ACCEPT_COOKIES_BUTTON).click(timeout=5000)
                        except:
                            pass
                        
                        # Handle image mode
                        if request_type == "image":
                            # Select model for image generation
                            combobox_elements = page.get_by_role("combobox").all()
                            i = 0
                            for combobox in combobox_elements:
                                try:
                                    sentry_element = combobox.get_attribute("data-sentry-element")
                                    sentry_file = combobox.get_attribute("data-sentry-source-file")
                                    
                                    if sentry_element == "Button" and sentry_file == "model-dropdown.tsx":
                                        i += 1
                                        if i == 2:
                                            combobox.click(timeout=5000)
                                            sleep(1)
                                            try:
                                                page.get_by_text("seedream-4").first.click(timeout=5000)
                                            except:
                                                try:
                                                    page.get_by_text("flux-1-kontext-pro").first.click(timeout=5000)
                                                except:
                                                    page.get_by_text("qwen-image-edit").first.click(timeout=5000)
                                            break
                                except:
                                    continue
                            
                            # Upload sample image if needed
                            # Note: This would need a real image path in production
                            # input_files = page.locator('input[type="file"][accept*="image"]').all()
                            # for input_file in input_files:
                            #     try:
                            #         input_file.set_input_files("path/to/image.png")
                            #         break
                            #     except:
                            #         pass
                        
                        # Fill in the prompt
                        try:
                            page.wait_for_selector(SEL_INPUT, state="visible", timeout=10000)
                            page.locator(SEL_INPUT).fill(user_message)
                        except:
                            pass
                        
                        # Submit
                        try:
                            page.wait_for_selector(SEL_SUBMIT_BUTTON, state="visible", timeout=10000)
                            page.locator(SEL_SUBMIT_BUTTON).click()
                        except:
                            pass
                        
                        # Confirm if needed
                        try:
                            page.wait_for_selector(SEL_OK_BUTTON, state="visible", timeout=10000)
                            page.locator(SEL_OK_BUTTON).click()
                        except:
                            pass
                        
                        # Wait for response (especially for images)
                        if request_type == "image":
                            try:
                                page.wait_for_selector(SEL_IMG_3, state="visible", timeout=120000)
                                page.wait_for_selector(SEL_IMG_1, state="visible", timeout=120000)
                            except:
                                pass
                        else:
                            # Wait for text response
                            sleep(10)
                        
                        return page
                    except Exception as e:
                        raise RuntimeError(f"Automation failed: {e}")
                
                # Try different fetch methods with fallback
                errors = []
                resp = None

                # Method 1: StealthyFetcher with solve_cloudflare=True (strict)
                try:
                    # Use Firefox-consistent headers; avoid Chromium-only client hints to prevent conflicts
                    extra_headers = {
                        "accept-language": "en-US,en;q=0.9",
                        "upgrade-insecure-requests": "1",
                    }
                    resp = StealthyFetcher.fetch(
                        target_url,
                        page_action=automate,
                        network_idle=True,
                        solve_cloudflare=True,
                        humanize=True,
                        headless=True,
                        extra_headers=extra_headers,
                    )
                    if resp:
                        result = {"content": "", "sources": [], "raw_sources_text": ""}
                        if request_type == "image":
                            try:
                                img1 = resp.css_first(f"{SEL_IMG_1}::attr(src)")
                                img3 = resp.css_first(f"{SEL_IMG_3}::attr(src)")
                                result["images"] = {"img1": img1, "img3": img3}
                            except Exception:
                                result["images"] = {"img1": None, "img3": None}
                        else:
                            text = resp.get_all_text()
                            result = clean_and_separate_text(text, user_message)
                        return result
                except Exception as e:
                    errors.append(f"StealthyFetcher(solve_cf): {str(e)}")
                
                # Method 1: Try direct Playwright first (avoids header generation issues)
                try:
                    from playwright.sync_api import sync_playwright  # type: ignore
                    
                    with sync_playwright() as p:
                        browser = p.chromium.launch(
                            headless=True,
                            args=[
                                "--no-sandbox",
                                "--disable-dev-shm-usage",
                                "--disable-blink-features=AutomationControlled",
                                "--disable-features=site-per-process",
                                "--disable-web-security",
                            ]
                        )
                        context = browser.new_context(
                            viewport={"width": 1920, "height": 1080},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                        page = context.new_page()
                        
                        # Run automation with Playwright page
                        automate(page)
                        
                        # Get content
                        html_content = page.content()
                        text_content = page.evaluate("() => document.body.innerText")
                        
                        # Extract images if needed
                        images = {}
                        if request_type == "image":
                            try:
                                img1_elem = page.query_selector(SEL_IMG_1)
                                img3_elem = page.query_selector(SEL_IMG_3)
                                images["img1"] = img1_elem.get_attribute("src") if img1_elem else None
                                images["img3"] = img3_elem.get_attribute("src") if img3_elem else None
                            except:
                                images = {"img1": None, "img3": None}
                        
                        browser.close()
                        
                        # Process results
                        if request_type == "image":
                            result = {
                                "content": text_content if text_content else "",
                                "sources": [],
                                "raw_sources_text": "",
                                "images": images
                            }
                        else:
                            result = clean_and_separate_text(text_content, user_message)
                            if request_type == "image":
                                result["images"] = images
                        
                        return result
                        
                except Exception as e:
                    errors.append(f"Playwright: {str(e)}")
                
                # Method 2: Try StealthyFetcher with relaxed options
                try:
                    resp = StealthyFetcher.fetch(
                        target_url,
                        page_action=automate,
                        network_idle=True,
                        solve_cloudflare=False,  # Disable to avoid header generation
                        humanize=False,  # Disable to avoid header issues
                        headless=True
                    )
                    
                    if resp:
                        result = {"content": "", "sources": [], "raw_sources_text": ""}
                        
                        if request_type == "image":
                            try:
                                img1 = resp.css_first(f"{SEL_IMG_1}::attr(src)")
                                img3 = resp.css_first(f"{SEL_IMG_3}::attr(src)")
                                result["images"] = {"img1": img1, "img3": img3}
                            except:
                                result["images"] = {"img1": None, "img3": None}
                        else:
                            text = resp.get_all_text()
                            result = clean_and_separate_text(text, user_message)
                        
                        return result
                        
                except Exception as e:
                    errors.append(f"StealthyFetcher: {str(e)}")
                
                # Method 3: Try basic Fetcher (no automation, just static)
                try:
                    from scrapling.fetchers import Fetcher  # type: ignore
                    basic_resp = Fetcher.fetch(target_url)
                    
                    if basic_resp:
                        if hasattr(basic_resp, 'get_all_text'):
                            text = basic_resp.get_all_text()
                        elif hasattr(basic_resp, 'text'):
                            text = basic_resp.text
                        else:
                            text = str(basic_resp)
                        
                        return {
                            "content": text[:1000] + "... (Note: Limited functionality without browser automation)",
                            "sources": [],
                            "raw_sources_text": "",
                            "error": "Fallback to basic fetcher - limited functionality"
                        }
                except Exception as e:
                    errors.append(f"Fetcher: {str(e)}")
                
                # All methods failed
                return {
                    "error": "All fetch methods failed: " + " | ".join(errors),
                    "error_type": "MultiFetchError"
                }
            
            result = await loop.run_in_executor(None, run_lmarena_session)
            return result
            
        except Exception as e:
            return {"error": str(e), "error_type": "ExecutorError"}
        
    
    return server


if __name__ == "__main__":
    server = create_server()
    server.run(transport="http", port=8081)