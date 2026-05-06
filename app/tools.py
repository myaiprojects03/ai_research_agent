from langchain.tools import tool
from duckduckgo_search import DDGS
import time

@tool
def duckduckgo_search(query: str) -> str:
    """Search the web for information about a topic using DuckDuckGo."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n")
                time.sleep(0.3) 
        
        if not results:
            return "No results found for this query."
        
        return "\n---\n".join(results)
    except Exception as e:
        return f"Search error: {str(e)}"