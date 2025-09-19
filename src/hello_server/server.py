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
    async def arena_session(request_type: str, user_message: str, image_path: str | None = None, ctx: Context | None = None) -> dict:
        """Automate a session on lmarena.ai and return cleaned content and sources.
        request_type: "image" | "web_search" | "search" | "text".
        user_message: the text to send.
        image_path: optional path to an image file to upload when request_type == "image".
        """
        try:
            # Lazy imports
            from scrapling.fetchers import StealthyFetcher  # type: ignore
            from time import sleep
            import re, os, traceback
            from typing import Any
        except Exception as e:
            return {"error": str(e) or repr(e), "error_type": e.__class__.__name__}

        # Selectors (provided by user)
        SEL_OPEN_MENU_BTN = r'button.border-border:nth-child(1)'
        SEL_SIDE_BY_SIDE_TEXT = "div.hover\:bg-surface-highlight:nth-child(2)"
        SEL_TOP_RIGHT_BUTTON = r'.max-w-full > div:nth-child(2) > div:nth-child(1) > form:nth-child(1) > div:nth-child(1) > div:nth-child(3) > div:nth-child(1) > div:nth-child(2) > button:nth-child(2)'
        SEL_INPUT = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div.flex.w-full.flex-1.flex-col.items-center.justify-center.px-4 > div > div.relative.hidden.w-full.max-w-full.sm\:block > div.bg-surface-primary.relative.flex.flex-col.rounded-\[0\.9rem\].md\:items-center.md\:gap-2 > div > form > div.flex.w-full.flex-col.justify-between.gap-1.md\:gap-2 > textarea'
        SEL_SUBMIT_BUTTON = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div.flex.w-full.flex-1.flex-col.items-center.justify-center.px-4 > div > div.relative.hidden.w-full.max-w-full.sm\:block > div.bg-surface-primary.relative.flex.flex-col.rounded-\[0\.9rem\].md\:items-center.md\:gap-2 > div > form > div.flex.w-full.flex-col.justify-between.gap-1.md\:gap-2 > div > div.flex.items-center.gap-2 > button'
        SEL_OK_BUTTON = r'button.px-4:nth-child(1)'
        SEL_ACCEPT_COOKIES_BUTTON = r'button.py-3:nth-child(2)'
        SEL_CLOUDFLARE_CHECKBOX = r'.cb-lb > input:nth-child(1)'
        SEL_TRANSITION_OPACITY = r'div.transition-opacity'
        SEL_FILE_UPLOAD_BUTTON = r'.sm\:block > div:nth-child(2) > div:nth-child(1) > form:nth-child(1) > div:nth-child(1) > div:nth-child(3) > div:nth-child(1) > button:nth-child(1)'
        SEL_FILE_INPUT = r'.sm\:block > div:nth-child(2) > div:nth-child(1) > form:nth-child(1) > div:nth-child(1) > input:nth-child(1)'
        SEL_IMG_3 = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div > div > div.relative.overflow-hidden.-mb-4.min-h-0.flex-1 > div > div > div > div > ol > div.flex.min-w-0.flex-col.gap-2.lg\:flex-row.lg\:gap-3 > div:nth-child(3) > div.no-scrollbar.relative.flex.w-full.flex-1.flex-col.overflow-x-auto.border-border-faint.border-t > div > div.flex.w-full.flex-row.items-center.gap-2.justify-center > div > div > img'
        SEL_IMG_1 = r'#chat-area > div.flex.min-h-0.flex-1.justify-center.overflow-hidden.overscroll-none > main > div > div > div.relative.overflow-hidden.-mb-4.min-h-0.flex-1 > div > div > div > div > ol > div.flex.min-w-0.flex-col.gap-2.lg\:flex-row.lg\:gap-3 > div:nth-child(1) > div.no-scrollbar.relative.flex.w-full.flex-1.flex-col.overflow-x-auto.border-border-faint.border-t > div > div.flex.w-full.flex-row.items-center.gap-2.justify-center > div > div > img'

        url = "https://lmarena.ai/?mode=direct"
        url_image = "https://lmarena.ai/?mode=side-by-side&chat-modality=image"
        url_web_search = "https://lmarena.ai/?chat-modality=search&mode=direct"

        def clean_and_separate_text(raw_text: str, user_prompt: str | None = None) -> dict:
            # Clean and split content from sources
            lines = [ln.strip() for ln in (raw_text or "").splitlines()]
            lines = [ln for ln in lines if ln]
            url_re = re.compile(r'https?://\S+')
            number_re = re.compile(r'^\d+([.)])?$')
            navigation_items = {
                'lmarena', 'new chat', 'leaderboard', 'today', 'more', 'direct chat', 'login'
            }
            noise_prefixes = ('gemini-', 'message from', 'search')
            disclaimer_keywords = (
                'inputs are processed', 'your conversations', 'do not submit',
                'by continuing to use our services', 'may otherwise be disclosed publicly',
                'acknowledge and direct us'
            )
            model_line_re = re.compile(r'^(gpt|gemini|claude|llama|qwen|mixtral|mistral|deepseek|vicuna|falcon|phi|yi|cohere|command|sonnet|opus|haiku)[\w_.\-]*$', re.IGNORECASE)

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

            source_labels = {
                'sources','source','references','refs','links','citations',
                'المصادر','مصادر','المراجع','روابط','مراجع','المراجع والمصادر'
            }
            sources_start_idx = -1
            for i, ln in enumerate(lines):
                token = ln.strip(' :').lower()
                if token in source_labels:
                    sources_start_idx = i
                    break

            sources: list[dict] = []
            used_indices: set[int] = set()

            def add_source(num, title, url):
                if not url:
                    return
                m = url_re.search(url)
                if not m:
                    return
                url_clean = m.group(0).rstrip(').,;')
                t = (title or '').strip(' -–—:|')
                n = str(num).strip() if num is not None else ''
                if any(s['url'] == url_clean for s in sources):
                    return
                sources.append({'number': n, 'title': t, 'url': url_clean})

            end_of_sources_idx = sources_start_idx
            content_start_idx = -1

            if sources_start_idx != -1:
                i = sources_start_idx + 1
                while i < len(lines):
                    ln = lines[i]
                    if is_noise_line(ln):
                        break
                    if url_re.search(ln):
                        title = ''
                        j = i - 1
                        while j > sources_start_idx:
                            prev = lines[j]
                            if prev and not url_re.search(prev) and not number_re.match(prev):
                                title = prev
                                used_indices.add(j)
                                break
                            j -= 1
                        num = None
                        k = i - 1
                        while k > sources_start_idx:
                            if number_re.match(lines[k]):
                                digits = re.sub(r'\D', '', lines[k])
                                num = digits or lines[k]
                                used_indices.add(k)
                                break
                            if lines[k] and not url_re.search(lines[k]):
                                break
                            k -= 1
                        add_source(num, title, ln)
                        used_indices.add(i)
                        end_of_sources_idx = i + 1
                        i += 1
                        continue
                    if number_re.match(ln):
                        num_str = re.sub(r'\D', '', ln) or ln
                        title = lines[i + 1] if i + 1 < len(lines) else ''
                        url = ''
                        lookahead_limit = min(len(lines), i + 6)
                        for idx in range(i + 1, lookahead_limit):
                            if url_re.search(lines[idx]):
                                url = lines[idx]
                                used_indices.update({i, i + 1, idx})
                                end_of_sources_idx = idx + 1
                                i = idx + 1
                                break
                        else:
                            i += 1
                            continue
                        add_source(num_str, title, url)
                        continue
                    if (len(ln) > 60 and not number_re.match(ln) and not url_re.search(ln)):
                        break
                    i += 1
                for j in range(end_of_sources_idx if end_of_sources_idx != -1 else sources_start_idx + 1, len(lines)):
                    if lines[j] and not is_noise_line(lines[j]) and not url_re.search(lines[j]) and not number_re.match(lines[j]):
                        content_start_idx = j
                        break

            content_end_idx = len(lines)
            scan_start = content_start_idx if content_start_idx != -1 else 0
            for idx in range(scan_start, len(lines)):
                l = lines[idx].lower().strip()
                if (
                    l.startswith('message from') or
                    l.startswith('gemini-') or
                    l == 'search' or
                    'inputs are processed' in l or
                    'your conversations' in l or
                    'do not submit' in l or
                    'by continuing to use our services' in l or
                    'may otherwise be disclosed publicly' in l or
                    'acknowledge and direct us' in l
                ):
                    content_end_idx = idx
                    break

            if content_start_idx == -1:
                for i, ln in enumerate(lines):
                    if is_noise_line(ln) or url_re.search(ln) or number_re.match(ln):
                        continue
                    if len(ln) > 20 or re.search(r'[.!?]', ln) or re.search(r'\w{4,}\s+\w{4,}', ln):
                        content_start_idx = i
                        break
                if content_end_idx <= content_start_idx:
                    for i in range(content_start_idx + 1, len(lines)):
                        if is_noise_line(lines[i]) or lines[i].lower().startswith('gemini-'):
                            content_end_idx = i
                            break
                    else:
                        content_end_idx = len(lines)

            main_content: list[str] = []
            if content_start_idx != -1:
                for ln in lines[content_start_idx:content_end_idx]:
                    if is_noise_line(ln):
                        continue
                    if url_re.search(ln) or number_re.match(ln):
                        continue
                    main_content.append(ln)
            else:
                for ln in lines:
                    if is_noise_line(ln):
                        continue
                    if url_re.search(ln) or number_re.match(ln):
                        continue
                    main_content.append(ln)

            seen = set()
            deduped = []
            for ln in main_content:
                if ln in seen:
                    continue
                seen.add(ln)
                deduped.append(ln)
            main_content = deduped

            final_content = '\n'.join(main_content)
            raw_sources_text = ''
            if sources_start_idx != -1:
                end_raw = end_of_sources_idx if (end_of_sources_idx and end_of_sources_idx > sources_start_idx) else min(content_end_idx, len(lines))
                raw_sources_text = '\n'.join(lines[sources_start_idx:end_raw])
            return {
                'content': final_content,
                'sources': sources,
                'raw_sources_text': raw_sources_text
            }

        def chack_RooBot_Box(page: Any):
            print("chack_RooBot_Box")
            try:
                page.locator(SEL_ACCEPT_COOKIES_BUTTON).click(timeout=500)
            except Exception as e:
                print(f"Could not accept cookies: {e}")
            print("accept cookies")

            sleep(16)
            try:
                print("Looking for div.transition-opacity element...")
                page.wait_for_selector(SEL_TRANSITION_OPACITY, state="visible", timeout=600)
                element = page.locator(SEL_TRANSITION_OPACITY).first
                box = element.bounding_box()
                if box:
                    center_x = box["x"] + box["width"] / 2
                    center_y = box["y"] + box["height"] / 2
                    page.mouse.click(center_x, center_y)
                    print(f"Clicked on center of div.transition-opacity at ({center_x}, {center_y})")
                else:
                    print("Could not get bounding box for div.transition-opacity")
            except Exception as e:
                print(f"div.transition-opacity element not found or timeout - continuing... Error: {e}")
            try:
                page.locator(SEL_ACCEPT_COOKIES_BUTTON).click(timeout=500)
            except Exception as e:
                print(f"Could not accept cookies: {e}")
            


        def run_session(rt: str, prompt: str) -> dict:
            # Choose target URL
            target_url = url
            if rt == "image":
                target_url = url_image
            elif rt in ("web_search", "search"):
                target_url = url_web_search

            def automate(page: Any):
                print("page wait for 15 seconds")
                sleep(15)
                print("start automate")
                chack_RooBot_Box(page)

                if rt == "image" and image_path and os.path.exists(image_path):
                    try:
                        chack_RooBot_Box(page)
                        input_file = page.locator('input[type="file"][accept*="image"]').all()
                        print("get input_file")
                        for i in input_file:
                            try:
                                i.set_input_files(image_path)
                                break
                            except Exception as e:
                                print(f"Could not set input file: {e}")
                    except Exception as e:
                        chack_RooBot_Box(page)
                        print(f"Error locating image input: {e}")
                else:
                    chack_RooBot_Box(page)
                    print("waiting for text response")

                try:
                    chack_RooBot_Box(page)
                    page.wait_for_selector(SEL_INPUT, state="visible", timeout=10000)
                    page.locator(SEL_INPUT).fill(prompt)
                except Exception as e:
                    print("Input textarea not found or fill failed - continuing...", e)

                try:
                    print("waiting for submit button")
                    page.wait_for_selector(SEL_SUBMIT_BUTTON, state="visible", timeout=10000)
                    page.locator(SEL_SUBMIT_BUTTON).click()
                except Exception as e:
                    print("Submit button not found or click failed - continuing...", e)

                try:
                    print("waiting for ok button")
                    page.wait_for_selector(SEL_OK_BUTTON, state="visible", timeout=10000)
                    page.locator(SEL_OK_BUTTON).click()
                except Exception as e:
                    print("OK button not found or click failed - continuing...", e)

                return page

            try:
                try:
                    # Try with extended options first
                    resp = StealthyFetcher.fetch(
                        target_url,
                        page_action=automate,
                        solve_cloudflare=True,
                        headless=True,
                        network_idle=True,  # if unsupported, TypeError below
                        google_search=True,
                        humanize=True,
                    )
                except TypeError:
                    # Retry with minimal options if fetch signature differs
                    resp = StealthyFetcher.fetch(
                        target_url,
                        page_action=automate,
                        solve_cloudflare=True,
                        headless=True,
                    )
                except Exception as e:
                    # As a last retry, relax CF solving
                    try:
                        resp = StealthyFetcher.fetch(
                            target_url,
                            page_action=automate,
                            solve_cloudflare=False,
                            headless=True,
                        )
                    except Exception:
                        print(f"Could not fetch page: {e}")
                        return {"error": "FetchFailed", "error_type": "FetchFailed", "message": str(e)}

                if not resp:
                    return {"error": "EmptyResponse", "error_type": "EmptyResponse"}

                cleaned = {"images": {}, "raw_sources_text": "", "content": "", "sources": []}
                if rt == "image":
                    try:
                        img3 = resp.css_first(f"{SEL_IMG_3}::attr(src)")
                        img1 = resp.css_first(f"{SEL_IMG_1}::attr(src)")
                    except Exception:
                        img3 = None
                        img1 = None
                    cleaned["images"] = {"img1": img1, "img2": img3}
                    text = getattr(resp, 'get_all_text', lambda: '')()
                    cleaned.update(clean_and_separate_text(text, user_prompt=prompt))
                else:
                    text = getattr(resp, 'get_all_text', lambda: '')()
                    cleaned = clean_and_separate_text(text, user_prompt=prompt)
                return cleaned
            except Exception as e:
                tb = traceback.format_exc()
                print("arena_session error", e)
                return {"error": str(e) or repr(e), "error_type": e.__class__.__name__, "traceback": tb}

        return await asyncio.get_running_loop().run_in_executor(None, lambda: run_session(request_type, user_message))

    @server.tool()
    async def arena_text(user_message: str, ctx: Context) -> dict:
        """Send text to AI and receive response with cleaned content and sources."""
        return await arena_session("text", user_message, None, ctx)

    @server.tool()
    async def arena_search(user_message: str, ctx: Context) -> dict:
        """Search the web and return cleaned text response with sources."""
        return await arena_session("search", user_message, None, ctx)

    @server.tool()
    async def arena_image(user_message: str, image_path: str, ctx: Context) -> dict:
        """Generate AI images from text prompts and return image URLs.
        
        Args:
            user_message: Text prompt describing the image to generate
            image_path: Local path to an image file to upload for reference or style transfer
            
        Returns:
            Dictionary containing generated image URLs and metadata
        """
        return await arena_session("image", user_message, image_path, ctx)
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