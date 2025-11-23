import asyncio
import json
import httpx
from collections import deque
from typing import List, Set, Dict, Optional, AsyncGenerator
from .llm_client import verify_candidates_with_llm

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

# Persistent Cache Implementation
import os
import json
import asyncio

CACHE_FILE = "wiki_cache.json"
_page_cache = {}

def load_cache():
    global _page_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                _page_cache = json.load(f)
            print(f"Loaded {len(_page_cache)} items from cache.")
        except Exception as e:
            print(f"Failed to load cache: {e}")

def save_cache():
    global _page_cache
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(_page_cache, f)
    except Exception as e:
        print(f"Failed to save cache: {e}")

# Load cache on module import
load_cache()

import asyncio
import json
import httpx
from collections import deque
from typing import List, Set, Dict, Optional, AsyncGenerator
from .llm_client import verify_candidates_with_llm

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

# Persistent Cache Implementation
import os
import json
import asyncio

CACHE_FILE = "wiki_cache.json"
_page_cache = {}

def load_cache():
    global _page_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                _page_cache = json.load(f)
            print(f"Loaded {len(_page_cache)} items from cache.")
        except Exception as e:
            print(f"Failed to load cache: {e}")

def save_cache():
    global _page_cache
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(_page_cache, f)
    except Exception as e:
        print(f"Failed to save cache: {e}")

# Load cache on module import
load_cache()

class LevelBasedSearch:
    def __init__(self, start_page: str, end_page: str, client: httpx.AsyncClient):
        self.start_page = start_page
        self.end_page = end_page
        self.client = client
        
        # Queue: (node, path_to_node, depth)
        self.queue = deque([(start_page, [start_page], 0)])
        
        # Visited: node -> depth
        self.visited = {start_page: 0}
        
        # Config
        self.MAX_DEGREE = 10  # Only keep top 10 connections per node
        self.MAX_DEPTH = 10   # Stop at level 10
        self.semaphore = asyncio.Semaphore(5) # Limit concurrent tasks to 5
        
        self.step_count = 0

    async def search(self) -> AsyncGenerator[str, None]:
        """
        Executes the Level-Based Search (Forward) with Parallel Level Processing.
        Yields JSON status messages.
        """
        yield json.dumps({"status": "info", "message": f"Initializing Level-Based Search: {self.start_page} -> {self.end_page} (Max Depth: {self.MAX_DEPTH}, Max Degree: {self.MAX_DEGREE})"})

        while self.queue:
            self.step_count += 1
            
            # 1. Collect all nodes at the current depth
            current_depth = self.queue[0][2]
            level_nodes = []
            while self.queue and self.queue[0][2] == current_depth:
                level_nodes.append(self.queue.popleft())
            
            if current_depth >= self.MAX_DEPTH:
                break
                
            print(f"DEBUG: Processing Level {current_depth} with {len(level_nodes)} nodes in parallel...")
            
            # 2. Process them in parallel
            tasks = [self.process_node(node, path, depth) for node, path, depth in level_nodes]
            results = await asyncio.gather(*tasks)
            
            # 3. Handle results
            found_target = False
            for result in results:
                if result:
                    if result["found"]:
                        yield json.dumps({"status": "finished", "path": result["path"]})
                        found_target = True
                        # We found a path! But we might want to finish the level or just return.
                        # User asked for "a" path. Let's return.
                        return
                    
                    # Add children to queue
                    for child in result["children"]:
                        self.queue.append(child)
                        
                    # Yield status for the visited node
                    yield json.dumps({
                        "status": "visiting", 
                        "node": result["node"], 
                        "direction": "forward", 
                        "step": self.step_count, # This is level step now
                        "depth": current_depth
                    })
            
            if found_target:
                return

            save_cache()

        yield json.dumps({"status": "error", "message": f"Route cannot be found within depth {self.MAX_DEPTH}."})

    async def process_node(self, current_node, path, depth):
        """
        Process a single node: fetch, filter, verify, and return children.
        """
        async with self.semaphore:
            try:
                # 1. Get Data
                wiki_text, candidates = await self.get_page_data(current_node)
                
                # 2. Check if target is in candidates (Early Exit)
                if self.end_page in candidates:
                    print(f"DEBUG: Found target {self.end_page} in candidates of {current_node}")
                    return {"found": True, "path": path + [self.end_page], "node": current_node}

                # 3. Heuristic Filter
                filtered_candidates = self.heuristic_filter(candidates)
                
                # 4. LLM Verification & Ranking (Top 10)
                candidates_for_llm = filtered_candidates[:100]
                
                verified_objs = await verify_candidates_with_llm(
                    wiki_text, 
                    current_node, 
                    target_name=self.end_page, 
                    candidates=candidates_for_llm
                )
                
                valid_neighbors = [obj["name"] for obj in verified_objs]
                top_neighbors = valid_neighbors[:self.MAX_DEGREE]
                
                print(f"DEBUG: {current_node} - Verified: {len(valid_neighbors)} -> Keeping Top {len(top_neighbors)}")
                
                children = []
                for neighbor in top_neighbors:
                    if neighbor not in self.visited:
                        self.visited[neighbor] = depth + 1
                        children.append((neighbor, path + [neighbor], depth + 1))
                
                return {"found": False, "children": children, "node": current_node}
                
            except Exception as e:
                print(f"Error processing node {current_node}: {e}")
                return None

    async def get_page_data(self, title: str):
        # Check cache first
        global _page_cache
        if title in _page_cache:
            print(f"CACHE HIT: {title}")
            return _page_cache[title]
        
        # Fetch Intro + Links
        headers = {
            "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/capkimkhanh2k5/SixDegreeOfSeparation; capkimkhanh2k5@gmail.com)"
        }
        
        try:
            # Parallelize requests using asyncio.gather
            # 1. Text Request
            text_req = self.client.get(API_URL, params={
                "action": "query", "format": "json", "titles": title, 
                "prop": "extracts", "explaintext": 1, "exintro": 1
            }, headers=headers)
            
            # 2. Links Request (Initial)
            link_params = {
                "action": "query", "format": "json", "titles": title,
                "prop": "links", "plnamespace": 0, "pllimit": "max" # Request max allowed (500 for users)
            }
            link_req = self.client.get(API_URL, params=link_params, headers=headers)
            
            # Execute initial requests concurrently
            text_resp, link_resp = await asyncio.gather(text_req, link_req)
            
            # Process Text
            text_data = text_resp.json()
            pages = text_data.get("query", {}).get("pages", {})
            text = ""
            for _, p in pages.items(): text = p.get("extract", "")
            
            # Process Links (with Pagination)
            link_data = link_resp.json()
            links = []
            
            # Extract first batch
            for page_id, page_data in link_data.get("query", {}).get("pages", {}).items():
                if "links" in page_data:
                    links.extend([link["title"] for link in page_data["links"]])
            
            # Check for 'continue' to fetch more links
            while "continue" in link_data:
                # print(f"DEBUG: Pagination triggered for {title}...")
                continue_params = link_params.copy()
                continue_params.update(link_data["continue"])
                
                link_resp = await self.client.get(API_URL, params=continue_params, headers=headers)
                link_data = link_resp.json()
                
                for page_id, page_data in link_data.get("query", {}).get("pages", {}).items():
                    if "links" in page_data:
                        links.extend([link["title"] for link in page_data["links"]])
                
                # Safety break
                if len(links) > 3000:
                    break
            
            # Store in cache
            result = (text, links)
            _page_cache[title] = result
            return result
        except Exception as e:
            print(f"ERROR in get_page_data for {title}: {e}")
            return "", []

    def heuristic_filter(self, candidates: List[str]) -> List[str]:
        # Filter out obvious non-people
        filtered = []
        
        # Keywords that strongly suggest non-people (lowercase for easier matching)
        exclude_keywords = [
            "list of", "award", "film", "movie", "album", "song", "band", "group",
            "discography", "videography", "bibliography", "tour", "concert",
            "season", "episode", "game", "championship", "tournament", "cup",
            "university", "college", "school", "hospital", "station", "airport",
            "park", "bridge", "building", "street", "avenue", "road", "highway",
            "river", "lake", "mountain", "ocean", "sea", "island", "bay",
            "template:", "category:", "portal:", "help:", "wikipedia:", "file:",
            "(city)", "(place)", "republic", "kingdom", "empire", "state", "province",
            "war", "battle", "treaty", "history", "politics", "election",
            "company", "organization", "party", "government", "agency",
            "location", "place", "city", "country", "architecture", "structure",
            "series", "show", "single", "record", "family"
        ]
        
        for c in candidates:
            # Skip years/dates that are just numbers
            if c.isdigit(): continue
            if len(c) <= 3 and c[0].isdigit(): continue
            
            # Check against exclusion keywords (case-insensitive)
            c_lower = c.lower()
            is_excluded = False
            for k in exclude_keywords:
                if k in c_lower:
                    is_excluded = True
                    break
            
            if is_excluded: continue
            
            # Keep everything else
            filtered.append(c)
        return filtered

# Wrapper for main.py
async def find_shortest_path(start_page: str, end_page: str):
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(limits=limits, timeout=180.0) as client:
        # Use LevelBasedSearch instead of BFS_Search
        searcher = LevelBasedSearch(start_page, end_page, client)
        async for msg in searcher.search():
            yield msg
