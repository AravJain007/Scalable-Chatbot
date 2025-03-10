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
        """Search the web for the given query"""
        try:
            # Call the web search service
            response = requests.post(
                f"{self.web_search_url}/search",
                json={
                    "query": query,
                    "max_results": max_results
                }
            )
            
            if response.status_code == 200:
                # Process and return the results
                results = response.json().get("results", [])
                
                # Format the results for better readability
                formatted_results = []
                for result in results:
                    # Clean up the content
                    content = result.get("content", "").strip()
                    if content:
                        formatted_results.append({
                            "text": f"Title: {result.get('title', 'No Title')}\n\nContent: {content}",
                            "source": result.get('url', 'Unknown Source')
                        })
                
                return formatted_results
            else:
                print(f"Error searching web: {response.text}")
                return [{"text": f"Error searching web: {response.status_code}", "source": "None"}]
                
        except Exception as e:
            print(f"Error connecting to web search service: {e}")
            return [{"text": f"Error connecting to web search service: {str(e)}", "source": "None"}]