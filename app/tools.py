from langchain.tools import tool
from duckduckgo_search import DDGS
import time

@tool
def duckduckgo_search(query: str) -> str:
    """Search the web for information about a topic using DuckDuckGo."""
    try:
        results = []
        ddgs = DDGS()
        search_results = ddgs.text(query, max_results=5)

        for r in search_results:
            title   = r.get("title", "No title")
            url     = r.get("href", "")
            summary = r.get("body", "No summary")
            results.append(f"Title: {title}\nURL: {url}\nSummary: {summary}")
            time.sleep(0.3)

        if not results:
            return f"No results found for: {query}"

        return "\n---\n".join(results)

    except Exception as e:
        return f"Search failed: {str(e)}"