from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import json
import os
import re
from dotenv import load_dotenv

from .bfs import find_shortest_path
from .text_utils import smart_name_search, resolve_wikipedia_name

load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:5173"],
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
        "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
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

@app.get("/api/search")
async def search_wikipedia(q: str = Query(..., min_length=1)):
    """
    Search Wikipedia for people only.
    Uses generator=prefixsearch to find titles starting with query,
    and filters results based on title and description to ensure they are humans.
    """
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            url = "https://en.wikipedia.org/w/api.php"
            
            # Use generator=prefixsearch to get results + properties in one go
            params = {
                "action": "query",
                "format": "json",
                "generator": "prefixsearch",
                "gpssearch": q,
                "gpslimit": 20, # Fetch more to allow for filtering
                "prop": "pageterms|pageimages|description", # Get description and images
                "wbptterms": "description",
                "piprop": "thumbnail",
                "pithumbsize": 50,
                "pilimit": 20
            }
            
            response = await client.get(url, params=params)
            data = response.json()
            
            # Results are in pages dict, need to sort by index or relevance?
            # prefixsearch returns pages, but order might be lost in dict?
            # Actually, generator results are usually unordered in the dict.
            # But prefixsearch usually returns them in relevance order in the 'query' -> 'pages' list?
            # No, 'pages' is a dict by pageid.
            # To get order, we might need 'index' property if available, or just trust the dict order (Python 3.7+ preserves insertion order if JSON decoder does).
            # But Wikipedia API JSON output for pages is usually by pageid (numeric).
            # Wait, `generator` output is unordered.
            # If we want order, we might need to use `action=opensearch` for order, then fetch details?
            # OR check if `index` is in the response.
            # `generator` output typically has `index` attribute in the page object.
            
            pages_dict = data.get("query", {}).get("pages", {})
            
            # Convert to list and sort by index if available
            pages_list = []
            for page_id, page in pages_dict.items():
                page["pageid"] = page_id
                pages_list.append(page)
            
            # Sort by index (if present)
            pages_list.sort(key=lambda x: x.get("index", 999))
            
            filtered_results = []
            
            # Keywords that strongly suggest a person
            person_keywords = [
                "born", "actor", "actress", "singer", "politician", "player", 
                "king", "queen", "prince", "princess", "president", "minister",
                "artist", "writer", "director", "musician", "rapper", "model",
                "comedian", "philosopher", "scientist", "inventor", "business",
                "magnate", "monarch", "emperor", "footballer", "athlete", "given name",
                "socialite", "personality", "human", "people", "author", "journalist", "activist",
                "revolutionary", "general", "officer", "leader"
            ]
            
            # Keywords that strongly suggest non-people
            exclude_keywords = [
                "film", "movie", "series", "episode", "album", "song", "band", "group",
                "novel", "book", "video game", "television", "show", "franchise",
                "soundtrack", "discography", "bridge", "structure", "building", 
                "transport", "station", "airport", "park", "place", "city", "capital",
                "village", "town", "district", "province", "state", "country",
                "river", "mountain", "lake", "sea", "ocean", "island", "planet",
                "disambiguation", "list of", "school", "university", "college",
                "photograph", "painting", "sculpture", "organization", "company"
            ]
            
            # Title exclusion patterns
            title_exclude_patterns = ["(photo)", "(film)", "(song)", "(book)", "(place)", "(band)", "(album)", "(city)", "(planet)"]

            for page in pages_list:
                title = page.get("title")
                if not title:
                    continue
                
                # Get description from pageterms (Wikidata) or description (Short Description)
                description = ""
                if "terms" in page and "description" in page["terms"]:
                    description = page["terms"]["description"][0]
                elif "description" in page:
                    description = page["description"]
                
                description_lower = description.lower()
                title_lower = title.lower()
                
                # 1. Reject based on Title
                if any(x in title_lower for x in title_exclude_patterns):
                    continue
                
                # Special case for cities
                if title in ["Paris", "London", "Berlin", "Tokyo", "New York"] and ("capital" in description_lower or "city" in description_lower):
                    continue

                # 2. Reject based on Description
                desc_tokens = set(re.findall(r'\b\w+\b', description_lower))
                
                is_excluded = any(k in desc_tokens for k in exclude_keywords)
                if is_excluded:
                    continue
                    
                # 3. Keep if Person
                is_person = any(k in desc_tokens for k in person_keywords)
                
                # Also accept if description is empty (might be a person without description) 
                # UNLESS title looks suspicious? No, let's be lenient with empty descriptions for now.
                if is_person or not description:
                    filtered_results.append(title)
                    if len(filtered_results) >= 10:
                        break
                        
            return filtered_results
            
        except Exception as e:
            print(f"Error searching Wikipedia: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch suggestions")

@app.get("/api/resolve-name")
async def resolve_name_endpoint(q: str = Query(..., min_length=1)):
    """
    Resolves a name to its correct Wikipedia title.
    Handles diacritics, typos, and alternate spellings.
    """
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
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

@app.post("/api/shortest-path")
async def get_shortest_path(request: PathRequest):
    # Auto-resolve names
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
    }
    
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as resolve_client:
        start_page = await resolve_wikipedia_name(request.start_page, resolve_client) or request.start_page
        end_page = await resolve_wikipedia_name(request.end_page, resolve_client) or request.end_page
    
    print(f"Resolved: {request.start_page} -> {start_page}")
    print(f"Resolved: {request.end_page} -> {end_page}")

    async def event_generator():
        try:
            async for message in find_shortest_path(start_page, end_page):
                data = json.loads(message)
                if data["status"] == "finished":
                    # Fetch details for the final path
                    path_nodes = data["path"]
                    path_details = await get_page_details(path_nodes)
                    
                    # Generate context for edges
                    enriched_path = []
                    for i in range(len(path_nodes) - 1):
                        p1 = path_nodes[i]
                        p2 = path_nodes[i+1]
                        
                        # Find detail object
                        p1_detail = next((d for d in path_details if d.title == p1), None)
                        
                        context = await generate_relationship_context(p1, p2)
                        
                        if p1_detail:
                            enriched_path.append({
                                "node": p1_detail.dict(),
                                "edge_context": context
                            })
                    
                    # Add last node
                    last_node = path_nodes[-1]
                    last_detail = next((d for d in path_details if d.title == last_node), None)
                    if last_detail:
                        enriched_path.append({
                            "node": last_detail.dict(),
                            "edge_context": None # End of path
                        })

                    final_response = {"status": "finished", "path_with_context": enriched_path}
                    yield json.dumps(final_response) + "\n"
                else:
                    yield message + "\n"
        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# Static Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DIST_DIR = os.path.join(ROOT_DIR, "frontend", "dist")
ASSETS_DIR = os.path.join(DIST_DIR, "assets")

if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
else:
    print(f"WARNING: Assets directory not found at {ASSETS_DIR}")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    if full_path.startswith("api"):
         raise HTTPException(status_code=404, detail="Not Found")
    
    file_path = os.path.join(DIST_DIR, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
        
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return HTTPException(status_code=404, detail="Frontend not built. Run 'npm run build' in frontend directory.")
