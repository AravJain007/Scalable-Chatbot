import os
import requests
import json
from typing import List, Dict, Any
from backend.config import Config

class WebSearchAgent:
    """Agent for web search operations using Scrapy service"""
    
    def __init__(self):
        self.web_search_url = f"http://{Config.WEB_SEARCH_HOST}:{Config.WEB_SEARCH_PORT}/"
        self.allowed_domains = os.getenv("ALLOWED_DOMAINS", "").split(",")
        self.max_depth = int(os.getenv("MAX_DEPTH", "2"))
        self.scrape_timeout = int(os.getenv("SCRAPE_TIMEOUT", "60"))
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """
        Perform a web search for the given query
        Returns a list of search results with title, text, and source
        """
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
    
    def format_results_for_evaluation(self, results: List[Dict]) -> str:
        """
        Format search results for use in evaluation prompts
        """
        if not results:
            return "No search results available."
            
        formatted_results = ""
        for i, result in enumerate(results, 1):
            formatted_results += f"--- SOURCE {i} ---\n"
            formatted_results += f"Title: {result.get('title', 'No Title')}\n"
            formatted_results += f"URL: {result.get('source', 'Unknown')}\n"
            formatted_results += f"Content: {result.get('text', '')}\n\n"
            
        return formatted_results
        
    def execute_search_for_evaluation(self, query: str, callback=None) -> str:
        """
        Execute a search and format the results for LLM evaluation
        Includes progress callbacks if provided
        """
        if callback:
            callback("Searching the web for relevant information...")
            
        results = self.search(query)
        
        if callback:
            callback(f"Found {len(results)} relevant sources.")
            
        formatted_results = self.format_results_for_evaluation(results)
        return formatted_results