from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser

NEWS_CONFIG = {
    "cnn.com": {
        "title": "h1.pg-headline",
        "content": ".article__content p",
        "date": ".timestamp",
        "author": ".byline__name"
    },
    "bbc.com": {
        "title": "h1#main-heading",
        "content": "[data-component='text-block']",
        "date": "time",
        "author": "[role='region'] [data-testid='byline-name']"
    },
    "reuters.com": {
        "title": "h1.article-header__title__3Y2hh",
        "content": ".article-body__content__17Yit p",
        "date": "[data-testid='Timestamp']",
        "author": ".author-name__2XBtH"
    }
}

async def scrape_news(url: str):
    domain = url.split("//")[-1].split("/")[0]
    config = NEWS_CONFIG.get(domain)
    
    if not config:
        return {"error": "Unsupported news domain", "success": False}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            java_script_enabled=True
        )
        
        try:
            page = await context.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_selector(config["title"], timeout=30000)
            
            html = await page.content()
            tree = HTMLParser(html)
            
            return {
                "title": tree.css_first(config["title"]).text(),
                "content": " ".join([p.text() for p in tree.css(config["content"])]),
                "date": tree.css_first(config["date"]).text(),
                "author": tree.css_first(config["author"]).text(),
                "success": True
            }
            
        except Exception as e:
            return {"error": str(e), "success": False}
            
        finally:
            await browser.close()