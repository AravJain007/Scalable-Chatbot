from fastapi import FastAPI
from scrapers.generic_scraper import scrape_generic
import requests
import asyncio
from pydantic import BaseModel
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    max_results: int = 3  # Default value

# 1. Search Engine Scraper to Get URLs
async def get_search_results(query: str, max_results=5):
    logger.info(f"Searching for: {query}")
    try:
        # Add timeout to the request
        response = requests.get(
            "http://searxng:8080/",  # Use Docker service name
            params={
                "q": query,
                "format": "json",
                "categories": "general",
                "language": "en-US",
                "safesearch": "1",  # Enable safe search
                "pageno": 1
            },
            headers={"User-Agent": "Mozilla/5.0"},  # Mimic browser
            timeout=15  # 15 seconds timeout
        )
        
        # Check if the response is valid
        if response.status_code != 200:
            logger.error(f"SearXNG returned status code: {response.status_code}")
            return []
            
        # Extract URLs from results
        try:
            data = response.json()
            results = data.get("results", [])
            urls = [result["url"] for result in results[:max_results]]
            
            logger.info(f"Found {len(urls)} URLs")
            return urls
        except ValueError as e:
            logger.error(f"Failed to parse JSON from SearXNG: {e}")
            return []
    
    except requests.exceptions.Timeout:
        logger.error("SearXNG request timed out")
        return []
    except requests.exceptions.ConnectionError:
        logger.error("Connection error to SearXNG")
        return []
    except Exception as e:
        logger.error(f"SearXNG Error: {e}")
        return []
    
@app.post("/search")
async def handle_search(request: SearchRequest): 
    try:
        # Step 1: Get URLs from search engine
        urls = await get_search_results(request.query, request.max_results)
        
        if not urls:
            return {
                "query": request.query,
                "results": [],
                "message": "No URLs found from search",
                "success": False
            }
        
        # Step 2: Scrape all URLs concurrently, but with a timeout
        tasks = [scrape_generic(url) for url in urls]
        
        # Add a global timeout for all scraping tasks
        try:
            # Set a reasonable overall timeout (e.g., 45 seconds)
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=45
            )
            
            # Process results and handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error scraping {urls[i]}: {result}")
                    processed_results.append({
                        "url": urls[i],
                        "title": "",
                        "content": "",
                        "error": str(result),
                        "success": False
                    })
                else:
                    processed_results.append(result)
            
            # Filter out empty or failed results
            valid_results = [r for r in processed_results if r.get('success') and r.get('content')]
            
            if not valid_results:
                logger.warning("No valid content was scraped from any URL")
            
            return {
                "query": request.query,
                "results": valid_results,
                "total_urls": len(urls),
                "successful_scrapes": len(valid_results),
                "success": len(valid_results) > 0
            }
            
        except asyncio.TimeoutError:
            logger.error("Global timeout reached while scraping URLs")
            return {
                "query": request.query,
                "results": [],
                "message": "Timeout while scraping URLs",
                "success": False
            }
    
    except Exception as e:
        logger.error(f"Unexpected error in search handler: {e}")
        return {"error": str(e), "success": False}

@app.get("/health")
def health_check():
    return {"status": "healthy"}