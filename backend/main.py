from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from .bfs import find_shortest_path
from .text_utils import smart_name_search, resolve_wikipedia_name
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:5173"], # Updated to include frontend port
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
        "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/capkimkhanh2k5/SixDegreeOfSeparation; capkimkhanh2k5@gmail.com)"
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
    Smart search with fuzzy matching and name normalization.
    Handles names with/without diacritics, typos, and multiple languages.
    """
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/capkimkhanh2k5/SixDegreeOfSeparation; capkimkhanh2k5@gmail.com)"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            # Use smart name search for better fuzzy matching
            best_match, suggestions = await smart_name_search(q, client)
            
            if not suggestions:
                return []
            
            # Filter to only people using the existing logic
            url = "https://en.wikipedia.org/w/api.php"
            
            # Get descriptions for filtering
            params = {
                "action": "query",
                "format": "json",
                "titles": "|".join(suggestions[:10]),
                "prop": "pageterms",
                "wbptterms": "description"
            }
            
            response = await client.get(url, params=params)
            data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            
            # Keywords that strongly suggest a person
            person_keywords = [
                "born", "actor", "actress", "singer", "politician", "player", 
                "king", "queen", "prince", "princess", "president", "minister",
                "artist", "writer", "director", "musician", "rapper", "model",
                "comedian", "philosopher", "scientist", "inventor", "business",
                "magnate", "monarch", "emperor", "footballer", "athlete", "given name",
                "socialite", "personality", "human", "people", "author", "journalist", "activist"
            ]
            
            # Keywords that strongly suggest non-people
            exclude_keywords = [
                "film", "movie", "series", "episode", "album", "song", "band", "group",
                "novel", "book", "video game", "television", "show", "franchise",
                "soundtrack", "discography", "bridge", "structure", "building", 
                "transport", "station", "airport", "park", "place", "city", "capital",
                "village", "town", "district", "province", "state", "country",
                "river", "mountain", "lake", "sea", "ocean", "island", "planet",
                "disambiguation", "list of", "school", "university", "college"
            ]
            
            import re
            filtered_titles = []
            
            for _, page in pages.items():
                title = page.get("title")
                if not title:
                    continue
                    
                description = page.get("terms", {}).get("description", [""])[0].lower()
                title_lower = title.lower()
                
                # Explicit exclusions based on title patterns
                if any(x in title_lower for x in ["(band)", "(album)", "(song)", "(city)", "(planet)", "(place)"]):
                    continue
                
                # Special case for specific cities  
                if title in ["Paris", "London", "Berlin", "Tokyo", "New York"] and ("capital" in description or "city" in description):
                    continue

                # Tokenize description for word-based matching
                desc_tokens = set(re.findall(r'\b\w+\b', description))
                
                is_person = any(k in desc_tokens for k in person_keywords)
                is_excluded = any(k in desc_tokens for k in exclude_keywords)
                
                # Exclusion takes precedence
                if is_excluded:
                    continue
                
                # Include if it's a person OR description is empty (likely a name)
                if is_person or not description:
                    filtered_titles.append(title)
                    
            return filtered_titles[:10]
            
        except Exception as e:
            print(f"Error searching Wikipedia: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch suggestions")

@app.get("/api/resolve-name")
async def resolve_name_endpoint(q: str = Query(..., min_length=1)):
    """
    Resolves a name to its correct Wikipedia title.
    Handles diacritics, typos, and alternate spellings.
    
    Example: "nguyen van thieu" -> "Nguyễn Văn Thiệu"
    """
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            resolved, suggestions = await smart_name_search(q, client)
            
            return {
                "query": q,
                "resolved": resolved,
                "suggestions": suggestions[:5]
            }
        except Exception as e:
            print(f"Error resolving name: {e}")
            raise HTTPException(status_code=500, detail="Failed to resolve name")

            
        except Exception as e:
            print(f"Error searching Wikipedia: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch suggestions")

@app.post("/api/shortest-path")
async def get_shortest_path(request: PathRequest):
    # Auto-resolve names to handle diacritics, typos, etc.
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0"
    }
    
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as resolve_client:
        # Resolve both start and end names
        resolved_start = await resolve_wikipedia_name(request.start_page, resolve_client)
        resolved_end = await resolve_wikipedia_name(request.end_page, resolve_client)
        
        # Use resolved names or fall back to original
        start_page = resolved_start if resolved_start else request.start_page
        end_page = resolved_end if resolved_end else request.end_page
        
        # Log resolution for debugging
        if resolved_start != request.start_page:
            print(f"RESOLVED: '{request.start_page}' → '{resolved_start}'")
        if resolved_end != request.end_page:
            print(f"RESOLVED: '{request.end_page}' → '{resolved_end}'")
    
    print(f"Received request: Start='{start_page}', End='{end_page}'")
    
    async def event_generator():
        try:
            async for message in find_shortest_path(start_page, end_page):
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




# Get the directory of the current file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to root
ROOT_DIR = os.path.dirname(BASE_DIR)
DIST_DIR = os.path.join(ROOT_DIR, "frontend", "dist")
ASSETS_DIR = os.path.join(DIST_DIR, "assets")

# Mount the assets directory
if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
else:
    print(f"WARNING: Assets directory not found at {ASSETS_DIR}")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """
    Serve the React app for any other path (client-side routing).
    """
    # Don't catch API routes (though FastAPI prioritizes specific routes anyway)
    if full_path.startswith("api"):
         raise HTTPException(status_code=404, detail="Not Found")
    
    # Check if it's a file in the dist folder (like vite.svg)
    file_path = os.path.join(DIST_DIR, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
        
    # Otherwise return index.html
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return HTTPException(status_code=404, detail="Frontend not built. Run 'npm run build' in frontend directory.")

