import httpx
import asyncio
import json

async def inspect_categories():
    titles = ["Võ Nguyên Giáp"]
    
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(titles),
        "prop": "categories",
        "cllimit": "max",
        "redirects": 1
    }
    
    headers = {
        "User-Agent": "SixDegreesTest/1.0"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers)
        data = resp.json()
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            print(f"Page Keys: {page.keys()}")
            if "missing" in page:
                print(f"Page {page.get('title')} is MISSING")
            
            title = page.get("title")
            categories = [c["title"] for c in page.get("categories", [])]
            
            print(f"Title: {title}")
            for c in categories:
                print(f"  - {c}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(inspect_categories())
