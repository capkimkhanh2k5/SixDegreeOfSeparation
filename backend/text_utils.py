"""
Utility functions for text normalization and Wikipedia name resolution
"""
import unicodedata
import httpx
from typing import Optional, List, Tuple

def normalize_text(text: str) -> str:
    """
    Normalize text by removing diacritics and converting to lowercase.
    Useful for fuzzy matching across languages.
    
    Examples:
        "Nguyễn Văn Thiệu" -> "nguyen van thieu"
        "François Mitterrand" -> "francois mitterrand"
    """
    # Normalize to NFD (decomposed form)
    nfd = unicodedata.normalize('NFD', text)
    # Filter out combining characters (diacritics)
    without_diacritics = ''.join(
        char for char in nfd 
        if unicodedata.category(char) != 'Mn'
    )
    return without_diacritics.lower()

async def resolve_wikipedia_name(query: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Resolves a fuzzy name query to the correct Wikipedia article title.
    Uses Wikipedia's opensearch API which handles redirects and fuzzy matching.
    
    Args:
        query: User input (may have typos, missing diacritics, etc.)
        client: httpx AsyncClient
        
    Returns:
        Resolved Wikipedia article title, or None if not found
    """
    API_URL = "https://en.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/capkimkhanh2k5/SixDegreeOfSeparation; capkimkhanh2k5@gmail.com)"
    }
    
    try:
        # Method 1: OpenSearch API (handles fuzzy matching)
        response = await client.get(API_URL, params={
            "action": "opensearch",
            "format": "json",
            "search": query,
            "limit": 5,
            "namespace": 0
        }, headers=headers)
        
        data = response.json()
        if len(data) >= 2 and len(data[1]) > 0:
            # data[1] contains list of matching titles
            best_match = data[1][0]
            
            # Verify it's a real page and get canonical title
            verify_response = await client.get(API_URL, params={
                "action": "query",
                "format": "json",
                "titles": best_match,
                "redirects": 1
            }, headers=headers)
            
            verify_data = verify_response.json()
            pages = verify_data.get("query", {}).get("pages", {})
            
            for page_id, page_info in pages.items():
                if page_id != "-1":  # -1 means page doesn't exist
                    return page_info.get("title", best_match)
        
        # Method 2: Fallback to search API
        search_response = await client.get(API_URL, params={
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "srprop": "wordcount"
        }, headers=headers)
        
        search_data = search_response.json()
        results = search_data.get("query", {}).get("search", [])
        
        if results:
            # Return the top result
            return results[0]["title"]
            
    except Exception as e:
        print(f"Error resolving name '{query}': {e}")
    
    return None

async def get_name_variants(title: str, client: httpx.AsyncClient) -> List[str]:
    """
    Get common variants/redirects for a Wikipedia title.
    Useful for names that have multiple spellings.
    
    Returns:
        List of alternative names/redirects
    """
    API_URL = "https://en.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0"
    }
    
    variants = [title]
    
    try:
        # Get redirects pointing to this page
        response = await client.get(API_URL, params={
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "redirects",
            "rdlimit": "10"
        }, headers=headers)
        
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        
        for page_id, page_info in pages.items():
            if "redirects" in page_info:
                for redirect in page_info["redirects"]:
                    variants.append(redirect["title"])
                    
    except Exception as e:
        print(f"Error getting variants for '{title}': {e}")
    
    return variants

async def smart_name_search(query: str, client: httpx.AsyncClient) -> Tuple[Optional[str], List[str]]:
    """
    Smart search that:
    1. Finds the best matching Wikipedia article
    2. Returns alternative suggestions
    
    Returns:
        (best_match, suggestions_list)
    """
    # First try direct resolution
    resolved = await resolve_wikipedia_name(query, client)
    
    # Get multiple suggestions
    API_URL = "https://en.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0"
    }
    
    suggestions = []
    
    try:
        response = await client.get(API_URL, params={
            "action": "opensearch",
            "format": "json",
            "search": query,
            "limit": 10,
            "namespace": 0
        }, headers=headers)
        
        data = response.json()
        if len(data) >= 2:
            suggestions = data[1][:10]  # Top 10 suggestions
            
    except Exception as e:
        print(f"Error getting suggestions for '{query}': {e}")
    
    return (resolved, suggestions)
