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

class BFS_Search:
    def __init__(self, start_page: str, end_page: str, client: httpx.AsyncClient):
        self.start_page = start_page
        self.end_page = end_page
        self.client = client
        
        # Queues for Bi-directional Search
        self.queue_start = deque([start_page])
        self.queue_end = deque([end_page])
        
        # Visited Sets
        self.visited_start = {start_page: None} # Node -> Parent
        self.visited_end = {end_page: None}
        
        # State
        self.found_path = None
        self.step_count = 0

    async def search(self) -> AsyncGenerator[str, None]:
        """
        Executes the Bi-directional BFS loop.
        Yields JSON status messages.
        """
        yield json.dumps({"status": "info", "message": f"Initializing search: {self.start_page} <--> {self.end_page}"})

        max_steps = 5000  # Increased from 1000 to allow much deeper searches
        
        while self.queue_start and self.queue_end and self.step_count < max_steps:
            self.step_count += 1
            
            # Optimization: Expand the smaller queue
            if len(self.queue_start) <= len(self.queue_end):
                current_node = self.queue_start.popleft()
                direction = "forward"
                current_visited = self.visited_start
                other_visited = self.visited_end
            else:
                current_node = self.queue_end.popleft()
                direction = "backward"
                current_visited = self.visited_end
                other_visited = self.visited_start
            
            yield json.dumps({"status": "visiting", "node": current_node, "direction": direction, "step": self.step_count})
            
            # 1. Get Data (Text + Links/Backlinks)
            if direction == "forward":
                wiki_text, candidates = await self.get_page_data(current_node)
            else:
                # For backward search, we need pages that link TO the current node
                wiki_text, candidates = await self.get_backlinks_data(current_node)
            
            # Save cache periodically (every 50 steps)
            if self.step_count % 50 == 0:
                save_cache()

            print(f"DEBUG: {current_node} ({direction}) - Raw Candidates: {len(candidates)}")
            
            # CRITICAL OPTIMIZATION: Early Exit
            # If the target is directly in the candidates, we are done!
            target_to_check = self.end_page if direction == "forward" else self.start_page
            
            if target_to_check in candidates:
                print(f"DEBUG: Early Exit! Found {target_to_check} in {current_node}")
                neighbor = target_to_check
                if neighbor not in current_visited:
                    current_visited[neighbor] = current_node
                    # Ensure connection is recorded
                    current_visited[neighbor] = current_node 
                    path = self.reconstruct_path(neighbor, direction)
                    save_cache()
                    yield json.dumps({"status": "finished", "path": path})
                    return

            # 2. Heuristic Filter (Fast)
            filtered_candidates = self.heuristic_filter(candidates)
            print(f"DEBUG: {current_node} - Heuristic Filtered: {len(filtered_candidates)}")
            
            # 3. LLM Verification (Smart Layer)
            # Only verify if we have a reasonable number of candidates
            valid_neighbors = []
            
            if direction == "forward":
                # Limit candidates to top 150 to avoid overwhelming LLM
                candidates_for_llm = filtered_candidates[:150]
                
                # Verify with LLM
                # Batching if necessary (handled in llm_client or here)
                verified_objs = await verify_candidates_with_llm(wiki_text, current_node, target_name=self.end_page, candidates=candidates_for_llm)
                print(f"DEBUG: {current_node} - LLM Verified: {len(verified_objs)}")
                
                # Sort by priority (is_bridge)
                verified_objs.sort(key=lambda x: not x.get("is_bridge", False))
                
                valid_neighbors = [obj["name"] for obj in verified_objs]
                
                # Fallback: If LLM returns nothing (strict filter?), use heuristic candidates
                # This prevents dead ends due to over-filtering
                if not valid_neighbors and filtered_candidates:
                    print(f"DEBUG: {current_node} - LLM returned 0, falling back to heuristic (first 20)")
                    valid_neighbors = filtered_candidates[:20]
            else:
                # Backward search: Just use links (LLM verification is harder backwards without context)
                valid_neighbors = filtered_candidates

            for neighbor in valid_neighbors:
                if neighbor not in current_visited:
                    current_visited[neighbor] = current_node
                    self.queue_start.append(neighbor) if direction == "forward" else self.queue_end.append(neighbor)
                    
                    if neighbor in other_visited:
                        # Intersection Found!
                        current_visited[neighbor] = current_node # Ensure connection is recorded
                        path = self.reconstruct_path(neighbor, direction)
                        save_cache() # Save on finish
                        yield json.dumps({"status": "finished", "path": path})
                        return

        yield json.dumps({"status": "error", "message": "No path found."})

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
                print(f"DEBUG: Pagination triggered for {title}...")
                continue_params = link_params.copy()
                continue_params.update(link_data["continue"])
                
                link_resp = await self.client.get(API_URL, params=continue_params, headers=headers)
                link_data = link_resp.json()
                
                for page_id, page_data in link_data.get("query", {}).get("pages", {}).items():
                    if "links" in page_data:
                        links.extend([link["title"] for link in page_data["links"]])
                
                # Safety break to prevent infinite loops on massive pages (e.g. "United States")
                if len(links) > 3000:
                    print(f"DEBUG: Reached link limit (3000) for {title}")
                    break
            
            # Store in cache
            result = (text, links)
            _page_cache[title] = result
            return result
        except Exception as e:
            print(f"ERROR in get_page_data for {title}: {e}")
            return "", []

    async def get_backlinks_data(self, title: str):
        # Fetch Backlinks with Pagination
        headers = {
            "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/capkimkhanh2k5/SixDegreeOfSeparation; capkimkhanh2k5@gmail.com)"
        }
        params = {
            "action": "query", "format": "json", "list": "backlinks",
            "bltitle": title, "bllimit": "max", "blnamespace": 0
        }
        
        links = []
        try:
            while True:
                resp = await self.client.get(API_URL, params=params, headers=headers)
                data = resp.json()
                
                batch = [item["title"] for item in data.get("query", {}).get("backlinks", [])]
                links.extend(batch)
                
                if "continue" in data:
                    params.update(data["continue"])
                    if len(links) > 3000: # Safety limit
                        break
                else:
                    break
                    
            return "", links # No text for backlinks usually
        except Exception as e:
            print(f"ERROR in get_backlinks_data for {title}: {e}")
            return "", []

    def heuristic_filter(self, candidates: List[str]) -> List[str]:
        # Filter out obvious non-people, but keep everything else
        # Made less restrictive to improve path finding
        filtered = []
        for c in candidates:
            # Skip years/dates that are just numbers
            if c.isdigit(): continue
            if len(c) <= 3 and c[0].isdigit(): continue  # Skip short year-like strings
            
            # Skip Wikipedia meta pages
            if "Wikipedia:" in c: continue
            if "Help:" in c: continue
            if "Template:" in c: continue
            
            # Keep everything else including "List of" which might have people
            filtered.append(c)
        return filtered

    def reconstruct_path(self, meeting_node: str, direction: str) -> List[str]:
        # Reconstruct path from meeting node
        
        # Path from start to meeting_node
        path_start = []
        curr = meeting_node
        if direction == "forward":
            # If we found it going forward, meeting_node is in visited_start
            # and its parent is in visited_start.
            # The other side is visited_end, where meeting_node is also present (as key).
            pass
        
        # Let's trace back from meeting_node in BOTH maps.
        
        # Trace back to start
        curr = meeting_node
        while curr:
            path_start.append(curr)
            curr = self.visited_start.get(curr)
        path_start.reverse()
        
        # Trace back to end
        path_end = []
        curr = self.visited_end.get(meeting_node)
        while curr:
            path_end.append(curr)
            curr = self.visited_end.get(curr)
            
        # path_start ends with meeting_node
        # path_end starts with parent of meeting_node in visited_end
        
        return path_start + path_end

# Wrapper for main.py
async def find_shortest_path(start_page: str, end_page: str):
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(limits=limits, timeout=180.0) as client:  # Increased from 60s to 180s
        searcher = BFS_Search(start_page, end_page, client)
        async for msg in searcher.search():
            yield msg
