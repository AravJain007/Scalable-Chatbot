from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser
import random
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36"
]

async def scrape_generic(url: str):
    logger.info(f"Starting to scrape: {url}")
    try:
        async with async_playwright() as p:
            # Additional browser launch args to help with Docker environments
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",  # Overcome limited Docker resource issues
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-extensions"
                ]
            )
            
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 720},  # Reduced size to save resources
                java_script_enabled=True,
                ignore_https_errors=True  # Handle SSL certificate issues
            )
            
            # Add timeout for the entire operation
            try:
                page = await context.new_page()
                logger.info(f"Navigating to URL: {url}")
                
                # Reduce initial random delay
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Set a reasonable timeout and handle navigation timeouts
                response = await page.goto(
                    url, 
                    timeout=30000,  # 30 seconds timeout
                    wait_until="domcontentloaded"  # Less strict loading requirement
                )
                
                if not response:
                    logger.warning(f"No response received for {url}")
                    return {"url": url, "error": "No response", "success": False}
                
                # Check status code
                if response.status >= 400:
                    logger.warning(f"Error status code {response.status} for {url}")
                    return {"url": url, "error": f"HTTP status {response.status}", "success": False}
                
                # Wait for content with shorter timeout
                try:
                    await page.wait_for_selector("body", timeout=10000)
                except Exception as e:
                    logger.warning(f"Timeout waiting for body: {e}")
                    # Continue anyway, we might have partial content
                
                html = await page.content()
                tree = HTMLParser(html)
                
                # Extract title
                title = tree.css_first("title").text() if tree.css_first("title") else ""
                logger.info(f"Extracted title: {title[:50]}...")
                
                # Improved content extraction
                content_node = (
                    tree.css_first("article") or
                    tree.css_first("main") or
                    tree.css_first("div#content") or
                    tree.css_first("div.content") or
                    tree.css_first("body")
                )
                
                content = ""
                if content_node:
                    # Process content with paragraphs
                    paragraphs = content_node.css("p")
                    if paragraphs:
                        content = " ".join([p.text(strip=True) for p in paragraphs if p.text(strip=True)])
                    else:
                        content = content_node.text(deep=True, separator=" ", strip=True)
                    
                    content = content[:5000]  # Truncate
                
                logger.info(f"Content length: {len(content)} chars")
                
                if not content:
                    logger.warning(f"No content extracted for {url}")
                
                return {
                    "url": url,
                    "title": title,
                    "content": content,
                    "success": True
                }
                
            except asyncio.TimeoutError as e:
                logger.error(f"Timeout error for {url}: {e}")
                return {"url": url, "error": f"Timeout: {str(e)}", "success": False}
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return {"url": url, "error": str(e), "success": False}
            finally:
                await context.close()
        
    except Exception as e:
        logger.error(f"Critical error with Playwright: {e}")
        return {"url": url, "error": f"Critical error: {str(e)}", "success": False}