import httpx
import asyncio
import json

async def check_categories():
    titles = ["Donald Trump", "Vietnam War", "United Nations", "Barack Obama", "Paris"]
    
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(titles),
        "prop": "categories",
        "cllimit": "max"
    }
    
    headers = {
        "User-Agent": "SixDegreesTest/1.0"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers)
        data = resp.json()
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            title = page.get("title")
            categories = [c["title"] for c in page.get("categories", [])]
            
            is_human = False
            human_keywords = ["births", "deaths", "living people", "alumni", "people from"]
            
            for cat in categories:
                if any(k in cat.lower() for k in human_keywords):
                    is_human = True
                    break
            
            print(f"Title: {title}")
            print(f"Is Human: {is_human}")
            # print(f"Categories: {categories[:5]}...")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(check_categories())
