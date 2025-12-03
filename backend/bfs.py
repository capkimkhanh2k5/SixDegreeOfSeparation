import asyncio
import json
import httpx
from collections import deque
from typing import List, Set, Dict, Optional, AsyncGenerator, Tuple
from .llm_client import verify_candidates_with_llm
import os

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

# Persistent Cache Implementation
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

class BidirectionalLevelBasedSearch:
    def __init__(self, start_page: str, end_page: str, client: httpx.AsyncClient):
        self.start_page = start_page
        self.end_page = end_page
        self.client = client
        
        # Queues: (node, path_list)
        # Forward: Path from Start -> Node
        self.queue_f = deque([(start_page, [start_page])])
        # Backward: Path from End -> Node (reversed direction)
        self.queue_b = deque([(end_page, [end_page])])
        
        # Visited: node -> path_list
        self.visited_f = {start_page: [start_page]}
        self.visited_b = {end_page: [end_page]}
        
        # Config
        self.MAX_DEGREE = 15  # Slightly increased for better coverage
        self.MAX_DEPTH = 10   # Total path length limit
        self.semaphore = asyncio.Semaphore(10) # Increased concurrency
        
        self.step_count = 0

    async def search(self) -> AsyncGenerator[str, None]:
        """
        Executes Bidirectional BFS.
        Yields JSON status messages.
        """
        yield json.dumps({"status": "info", "message": f"Initializing Bidirectional Search: {self.start_page} <-> {self.end_page}"})

        while self.queue_f and self.queue_b:
            self.step_count += 1
            
            # Check if we exceeded depth (heuristic: sum of depths)
            # Since we don't store depth explicitly in queue for simplicity, we can check path length
            if len(self.queue_f[0][1]) + len(self.queue_b[0][1]) > self.MAX_DEPTH:
                yield json.dumps({"status": "error", "message": "Max depth exceeded."})
                return

            # Expand the smaller frontier
            if len(self.queue_f) <= len(self.queue_b):
                direction = "forward"
                queue = self.queue_f
                visited_own = self.visited_f
                visited_other = self.visited_b
            else:
                direction = "backward"
                queue = self.queue_b
                visited_own = self.visited_b
                visited_other = self.visited_f

            # Process one level
            # We pop all nodes at the current level to process them in parallel
            # But for simplicity and responsiveness, let's process a batch
            batch_size = 5
            level_nodes = []
            for _ in range(min(len(queue), batch_size)):
                level_nodes.append(queue.popleft())
            
            print(f"DEBUG: Processing {len(level_nodes)} nodes in {direction} direction...")
            
            tasks = [self.process_node(node, path, direction) for node, path in level_nodes]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if not result:
                    continue
                
                parent_node = result["node"]
                children = result["children"]
                
                yield json.dumps({
                    "status": "visiting",
                    "node": parent_node,
                    "direction": direction,
                    "step": self.step_count,
                    "found_count": len(children)
                })

                for child in children:
                    if child in visited_own:
                        continue
                    
                    new_path = result["path"] + [child]
                    visited_own[child] = new_path
                    queue.append((child, new_path))
                    
                    # Check for intersection
                    if child in visited_other:
                        path_f = self.visited_f[child] if direction == "forward" else self.visited_f[child]
                        path_b = self.visited_b[child] if direction == "backward" else self.visited_b[child]
                        
                        # Construct full path: Start -> ... -> Meeting -> ... -> End
                        # path_b is End -> ... -> Meeting. We need to reverse it.
                        # But wait, path_b is stored as [End, ..., Meeting]
                        # So we reverse path_b[:-1] and append?
                        # No, path_b is [End, Y, X, Meeting].
                        # We want Meeting -> X -> Y -> End.
                        # So we take path_b reversed.
                        # But path_b includes Meeting. path_f includes Meeting.
                        # path_f: [Start, A, Meeting]
                        # path_b: [End, B, Meeting]
                        # Full: [Start, A, Meeting, B, End]
                        
                        full_path_list = path_f[:-1] + path_b[::-1]
                        
                        yield json.dumps({"status": "finished", "path": full_path_list})
                        return
            
            save_cache()
            
        yield json.dumps({"status": "error", "message": "No path found."})

    async def process_node(self, current_node: str, path: List[str], direction: str):
        async with self.semaphore:
            try:
                # 1. Fetch Candidates
                if direction == "forward":
                    # Get outgoing links
                    wiki_text, candidates = await self.get_page_data(current_node)
                    target_for_llm = self.end_page
                else:
                    # Get incoming links (backlinks)
                    # For backward search, we don't have the "source" text easily.
                    # We just get a list of pages that link TO current_node.
                    candidates = await self.get_backlinks(current_node)
                    wiki_text = "" # No context for backlinks yet
                    target_for_llm = self.start_page

                # 2. Heuristic Filter
                filtered_candidates = self.heuristic_filter(candidates)
                
                # 3. Verification
                # For backward search, LLM verification is tricky without text.
                # We will skip LLM for backward search OR use a very lightweight check if needed.
                # For now, let's skip LLM for backward to be fast, but rely on strict Heuristics.
                # OR: We can just take the top N candidates.
                
                final_candidates = []
                
                if direction == "forward":
                    # Use LLM to verify and rank
                    candidates_for_llm = filtered_candidates[:60] # Limit input
                    verified_objs = await verify_candidates_with_llm(
                        wiki_text, 
                        current_node, 
                        target_name=target_for_llm, 
                        candidates=candidates_for_llm
                    )
                    final_candidates = [obj["name"] for obj in verified_objs]
                    
                    # Fallback if LLM returns nothing but we had candidates
                    if not final_candidates and candidates_for_llm:
                        print(f"DEBUG: {current_node} - LLM returned 0, falling back to top 10 heuristic candidates.")
                        final_candidates = candidates_for_llm[:10]
                else:
                    # Backward: Just take top filtered candidates (maybe random or just first few?)
                    # Backlinks are usually sorted by something? No.
                    # We'll take top 20 to avoid explosion.
                    final_candidates = filtered_candidates[:20]
                
                # Keep top N
                top_candidates = final_candidates[:self.MAX_DEGREE]
                
                return {"node": current_node, "children": top_candidates, "path": path}

            except Exception as e:
                print(f"Error processing node {current_node} ({direction}): {e}")
                return None

    async def get_page_data(self, title: str) -> Tuple[str, List[str]]:
        # Check cache
        if title in _page_cache:
            return _page_cache[title]
        
        headers = {
            "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
        }
        
        try:
            # Fetch Text and Links
            params_text = {
                "action": "query", "format": "json", "titles": title, 
                "prop": "extracts", "explaintext": 1, "exintro": 1
            }
            params_links = {
                "action": "query", "format": "json", "titles": title,
                "prop": "links", "plnamespace": 0, "pllimit": "max"
            }
            
            req_text = self.client.get(API_URL, params=params_text, headers=headers)
            req_links = self.client.get(API_URL, params=params_links, headers=headers)
            
            resp_text, resp_links = await asyncio.gather(req_text, req_links)
            
            # Parse Text
            data_text = resp_text.json()
            pages = data_text.get("query", {}).get("pages", {})
            text = ""
            for _, p in pages.items(): text = p.get("extract", "")
            
            # Parse Links
            data_links = resp_links.json()
            links = []
            while True:
                for _, p in data_links.get("query", {}).get("pages", {}).items():
                    if "links" in p:
                        links.extend([l["title"] for l in p["links"]])
                
                if "continue" in data_links:
                    cont = data_links["continue"]
                    params_links.update(cont)
                    resp_links = await self.client.get(API_URL, params=params_links, headers=headers)
                    data_links = resp_links.json()
                    if len(links) > 2000: break # Safety limit
                else:
                    break
            
            result = (text, links)
            _page_cache[title] = result
            return result
        except Exception as e:
            print(f"API Error (Forward) {title}: {e}")
            return "", []

    async def get_backlinks(self, title: str) -> List[str]:
        # We can cache backlinks too if we want, but let's keep it simple for now or use same cache?
        # Backlinks are different from forward links. Let's not mix in _page_cache unless we use a key prefix.
        # For now, no cache for backlinks to save memory/complexity.
        
        headers = {
            "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
        }
        
        try:
            params = {
                "action": "query", "format": "json", 
                "list": "backlinks", "bltitle": title, 
                "blnamespace": 0, "bllimit": "max"
            }
            
            resp = await self.client.get(API_URL, params=params, headers=headers)
            data = resp.json()
            
            backlinks = []
            while True:
                if "backlinks" in data.get("query", {}):
                    backlinks.extend([b["title"] for b in data["query"]["backlinks"]])
                
                if "continue" in data:
                    cont = data["continue"]
                    params.update(cont)
                    resp = await self.client.get(API_URL, params=params, headers=headers)
                    data = resp.json()
                    if len(backlinks) > 2000: break
                else:
                    break
            
            return backlinks
        except Exception as e:
            print(f"API Error (Backward) {title}: {e}")
            return []

    def heuristic_filter(self, candidates: List[str]) -> List[str]:
        filtered = []
        # Keywords to exclude (Wikipedia meta-pages and generic lists)
        exclude_keywords = [
            "list of", "category:", "template:", "portal:", "help:", "wikipedia:", "file:",
            "user:", "talk:", "special:", "mediawiki:", "draft:", "timedtext:", "module:",
            "disambiguation"
        ]
        
        for c in candidates:
            c_lower = c.lower()
            # Basic filters
            if c[0].isdigit(): continue # Years/Dates
            if c.startswith("List of"): continue
            
            is_excluded = False
            for k in exclude_keywords:
                if k in c_lower:
                    is_excluded = True
                    break
            
            if not is_excluded:
                filtered.append(c)
                
        return filtered

# Wrapper for main.py
async def find_shortest_path(start_page: str, end_page: str):
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        searcher = BidirectionalLevelBasedSearch(start_page, end_page, client)
        async for msg in searcher.search():
            yield msg
