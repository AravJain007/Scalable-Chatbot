import os
import requests
from typing import List, Dict, Any
import json
from backend.config import Config

class WebSearchAgent:
    """Agent for web search operations using Scrapy service"""
    
    def __init__(self):
        self.web_search_url = f"http://{Config.WEB_SEARCH_HOST}:{Config.WEB_SEARCH_PORT}/"
        self.allowed_domains = os.getenv("ALLOWED_DOMAINS", "").split(",")
        self.max_depth = int(os.getenv("MAX_DEPTH", "2"))
        self.scrape_timeout = int(os.getenv("SCRAPE_TIMEOUT", "60"))
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        try:
            response = requests.post(
                f"{self.web_search_url}/search",
                json={
                    "query": query,
                    "max_results": max_results
                }
            )
            
            if response.status_code == 200:
                raw_results = response.json().get("results", [])
                formatted = []
                for result in raw_results:
                    formatted.append({
                        "title": result.get("title", "No Title"),
                        "text": result.get("content", "").strip(),
                        "source": result.get("url", "Unknown")
                    })
                return formatted
            else:
                return [{"title": "Error", "text": f"HTTP {response.status_code}", "source": ""}]
        except Exception as e:
            return [{"title": "Error", "text": str(e), "source": ""}]