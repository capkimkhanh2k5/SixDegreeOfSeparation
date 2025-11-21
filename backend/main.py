from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from .bfs import find_shortest_path

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PathRequest(BaseModel):
    start_page: str
    end_page: str

class PageDetail(BaseModel):
    title: str
    url: str
    image_url: Optional[str] = None

class PathResponse(BaseModel):
    path: Optional[List[PageDetail]]
    error: Optional[str] = None

async def get_page_details(titles: List[str]) -> List[PageDetail]:
    """
    Fetches page details (URL, thumbnail) for a list of titles.
    """
    if not titles:
        return []
        
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(titles),
        "prop": "pageimages|info",
        "pithumbsize": 200,
        "inprop": "url"
    }
    
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/yourusername/six-degrees-wikipedia; your@email.com)"
    }
    
    details_map = {}
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.get(url, params=params)
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            
            for _, page in pages.items():
                title = page.get("title")
                page_url = page.get("fullurl", "")
                image_url = page.get("thumbnail", {}).get("source")
                details_map[title] = PageDetail(title=title, url=page_url, image_url=image_url)
        except Exception as e:
            print(f"Error fetching page details: {e}")
            
    # Return details in the original order of titles
    return [details_map.get(title, PageDetail(title=title, url=f"https://en.wikipedia.org/wiki/{title}")) for title in titles]

from fastapi.responses import StreamingResponse
import json

# ... (imports)

@app.get("/api/search")
async def search_wikipedia(q: str = Query(..., min_length=1)):
    """
    Proxies the search request to Wikipedia's PrefixSearch API to get descriptions for filtering.
    """
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "prefixsearch",
        "gpssearch": q,
        "gpslimit": 10,
        "prop": "pageterms",
        "wbptterms": "description"
    }
    
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/yourusername/six-degrees-wikipedia; your@email.com)"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return []
            
            # Convert pages dict to list and sort by index
            results = []
            for _, page in pages.items():
                results.append(page)
            
            # Sort by 'index' field to maintain relevance
            results.sort(key=lambda x: x.get("index", 999))
            
            # Keywords that strongly suggest a person
            person_keywords = [
                "born", "actor", "actress", "singer", "politician", "player", 
                "king", "queen", "prince", "princess", "president", "minister",
                "artist", "writer", "director", "musician", "rapper", "model",
                "comedian", "philosopher", "scientist", "inventor", "business",
                "magnate", "monarch", "emperor", "footballer", "athlete", "given name"
            ]
            
            # Keywords that strongly suggest non-people (Strict Mode)
            exclude_keywords = [
                "film", "movie", "series", "episode", 
                "novel", "book", "video game", "television", "show", "franchise",
                "soundtrack", "discography", "bridge", "structure", "building", 
                "transport", "station", "airport", "park", "place", "city", 
                "village", "town", "district", "province", "state", "country",
                "river", "mountain", "lake", "sea", "ocean", "island"
            ]
            
            filtered_titles = []
            for page in results:
                title = page.get("title")
                description = page.get("terms", {}).get("description", [""])[0].lower()
                title_lower = title.lower()
                
                # Check if it's likely a person
                is_person = any(k in description for k in person_keywords)
                is_excluded = any(k in description for k in exclude_keywords) or \
                              "(film)" in title_lower or "(movie)" in title_lower or \
                              "(song)" in title_lower or "(band)" in title_lower or \
                              "bridge" in title_lower or "station" in title_lower
                
                # If description is empty, we might want to include it if it looks like a name (heuristic)
                # But for now, let's be strict or allow if no exclusion keywords found
                if (is_person or not description) and not is_excluded:
                    filtered_titles.append(title)
                    
            return filtered_titles
            
        except Exception as e:
            print(f"Error searching Wikipedia: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch suggestions")

@app.post("/api/shortest-path")
async def get_shortest_path(request: PathRequest):
    print(f"Received request: Start='{request.start_page}', End='{request.end_page}'")
    
    async def event_generator():
        try:
            async for message in find_shortest_path(request.start_page, request.end_page):
                data = json.loads(message)
                if data["status"] == "finished":
                    # Fetch details for the final path
                    path_details = await get_page_details(data["path"])
                    final_response = {"status": "finished", "path": [p.dict() for p in path_details]}
                    yield json.dumps(final_response) + "\n"
                else:
                    yield message + "\n"
        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.get("/")
async def root():
    return {"message": "Wiki Shortest Path API is running"}
