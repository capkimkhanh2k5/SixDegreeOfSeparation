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
    def __init__(self):
        self.client = None
        self.start_page = None
        self.end_page = None
        self.MAX_DEGREE = 30
        self.MAX_DEPTH = 10
        self.step_count = 0
        self.semaphore = asyncio.Semaphore(20) # Limit concurrent requests
        
        # Queues and visited sets will be initialized in search()
        self.queue_f = None
        self.queue_b = None
        self.visited_f = None
        self.visited_b = None
        
        self.step_count = 0

    async def search(self, start_node: str, end_node: str) -> AsyncGenerator[str, None]:
        """
        Executes Bidirectional BFS.
        Yields JSON status messages.
        """
        self.start_page = start_node
        self.end_page = end_node
        
        import time
        start_time = time.time()
        TIMEOUT = 60  # seconds
        MAX_NODES_VISITED = 2000
        
        # Initialize queues and visited sets for a new search
        self.queue_f = deque([(self.start_page, [self.start_page])])
        self.visited_f = {self.start_page: [self.start_page]}
        
        self.queue_b = deque([(self.end_page, [self.end_page])])
        self.visited_b = {self.end_page: [self.end_page]}
        
        self.step_count = 0 # Reset step count for a new search
        
        # Configure client with higher concurrency limits
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
        async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
            self.client = client # Overwrite the client with the new one for this search
            
            yield json.dumps({"status": "info", "message": f"Initializing Bidirectional Search: {self.start_page} <-> {self.end_page}"})

            while self.queue_f and self.queue_b:
                # Safety Checks
                if time.time() - start_time > TIMEOUT:
                    yield json.dumps({"status": "error", "message": f"Search timed out after {TIMEOUT} seconds."})
                    return

                total_visited = len(self.visited_f) + len(self.visited_b)
                if total_visited > MAX_NODES_VISITED:
                    yield json.dumps({"status": "error", "message": f"Search limit exceeded ({MAX_NODES_VISITED} nodes)."})
                    return

                self.step_count += 1
                
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

                # Process one level (Batch size increased for concurrency)
                batch_size = 20
                level_nodes = []
                for _ in range(min(len(queue), batch_size)):
                    level_nodes.append(queue.popleft())
                
                # Notify UI
                current_nodes = [n[0] for n in level_nodes]
                yield json.dumps({
                    "status": "exploring", 
                    "direction": direction, 
                    "nodes": current_nodes,
                    "stats": {
                        "visited": total_visited,
                        "queue_f": len(self.queue_f),
                        "queue_b": len(self.queue_b),
                        "time": round(time.time() - start_time, 1)
                    }
                })
                
                tasks = [self.process_node(node, path, direction) for node, path in level_nodes]
                results = await asyncio.gather(*tasks)
                
                for result in results:
                    if not result:
                        continue
                        
                    node, children, path = result["node"], result["children"], result["path"]
                    
                    for child in children:
                        if child in visited_own:
                            continue
                            
                        new_path = path + [child]
                        visited_own[child] = new_path
                        queue.append((child, new_path))
                        
                        # Check for intersection
                        if child in visited_other:
                            # Path found!
                            path_a = new_path
                            path_b = visited_other[child]
                            
                            if direction == "forward":
                                full_path = path_a[:-1] + path_b[::-1]
                            else: # direction == "backward"
                                full_path = path_b[:-1] + path_a[::-1]
                                
                            yield json.dumps({"status": "finished", "path": full_path})
                            return

                # Depth limit check (optional, but good practice)
                if self.step_count > 100: # Safety break for loop count
                     yield json.dumps({"status": "error", "message": "Search depth limit exceeded."})
                     return
            
            yield json.dumps({"status": "not_found", "message": "No path found."})

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
                    candidates = await self.get_backlinks(current_node)
                    wiki_text = "" # No context for backlinks yet
                    target_for_llm = self.start_page

                # 2. Heuristic Filter (Name-based)
                filtered_candidates = self.heuristic_filter(candidates)
                
                # Shuffle to avoid alphabetical bias (e.g. getting stuck in "10th...", "11th...")
                import random
                random.shuffle(filtered_candidates)
                
                # 3. Strict Person Check (Category-based)
                # We can't check all, so let's take top 500 from heuristic and check them
                candidates_to_check = filtered_candidates[:500]
                human_candidates = await self.batch_check_categories(candidates_to_check)
                
                print(f"DEBUG: {current_node} - Candidates: {len(candidates)} -> Heuristic: {len(filtered_candidates)} -> Checked: {len(candidates_to_check)} -> Human: {len(human_candidates)}")

                # 4. LLM Verification (Optional - Disabled for speed/benchmark)
                # For strict person graph, category check is usually enough.
                # LLM is too slow (rate limits) for real-time BFS.
                final_candidates = human_candidates
                
                # If we have too many, take top N
                if len(final_candidates) > self.MAX_DEGREE:
                     final_candidates = final_candidates[:self.MAX_DEGREE]
                     
                return {
                    "node": current_node,
                    "children": final_candidates,
                    "path": path
                }
            except Exception as e:
                print(f"Error processing node {current_node} ({direction}): {e}")
                return None
    
    async def batch_check_categories(self, titles: List[str]) -> List[str]:
        """
        Checks if the given titles are humans based on Wikipedia categories.
        Returns a list of titles that are confirmed humans.
        """
        if not titles:
            return []
            
        # Chunk into batches of 10
        chunk_size = 10
        batches = [titles[i:i+chunk_size] for i in range(0, len(titles), chunk_size)]
        
        async def check_batch(batch):
            human_titles_batch = []
            # Ensure titles are properly encoded/joined
            titles_param = "|".join(batch)
            
            params = {
                "action": "query",
                "format": "json",
                "titles": titles_param,
                "prop": "categories",
                "cllimit": "max",
                "redirects": 1
            }
            
            headers = {
                "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
            }
            
            try:
                # Use semaphore to respect concurrency limits
                async with self.semaphore:
                    resp = await self.client.get(API_URL, params=params, headers=headers)
                
                if resp.status_code != 200:
                    print(f"API Error: Status {resp.status_code} for batch check")
                    return []
                    
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    print(f"API Error: Invalid JSON response for batch check. Response text: {resp.text[:100]}...")
                    return []
                    
                pages = data.get("query", {}).get("pages", {})
                for _, page in pages.items():
                    title = page.get("title")
                    
                    # Skip missing pages
                    if "missing" in page:
                        continue
                        
                    categories = [c["title"].lower() for c in page.get("categories", [])]
                    
                    # Strip "Category:" prefix for cleaner checks
                    clean_categories = []
                    for c in categories:
                        if c.startswith("category:"):
                            clean_categories.append(c[9:])
                        else:
                            clean_categories.append(c)
                    
                    # Strict Person Check
                    is_human = False
                    is_excluded = False
                    
                    # 1. Negative Filters (Exclude animals, fictional characters)
                    # "cat" is too dangerous as substring (matches "Category", "Catholic", etc.)
                    # Use specific animal terms or word boundaries if needed.
                    negative_keywords = ["animal", "horse", "racehorse", "fictional", "character"]
                    
                    for cat in clean_categories:
                        # Check full word match or specific phrases to avoid false positives
                        if any(k in cat for k in negative_keywords):
                            # Double check it's not "Animal rights activists" etc.
                            if "activist" in cat or "trainer" in cat or "owner" in cat or "breeder" in cat:
                                continue
                            is_excluded = True
                            break
                    
                    if is_excluded:
                        continue

                    # 2. Positive Filters (Must match at least one)
                    # "births" -> "1990 births" (avoid "births by...")
                    # "deaths" -> "2020 deaths" (avoid "deaths by...")
                    
                    for cat in categories:
                        if "living people" in cat:
                            is_human = True
                            break
                        if "people from" in cat:
                            is_human = True
                            break
                        if "alumni" in cat:
                            is_human = True
                            break
                        if "players" in cat:
                            is_human = True
                            break
                        if "actors" in cat or "actresses" in cat:
                            is_human = True
                            break
                        if "politicians" in cat:
                            is_human = True
                            break
                        if "singers" in cat or "musicians" in cat:
                            is_human = True
                            break
                        if "writers" in cat:
                            is_human = True
                            break
                        if "directors" in cat:
                            is_human = True
                            break
                        
                        # Check for Year Births/Deaths
                        # e.g., "Category:1946 births"
                        # We want to match "\d{4} births" exactly at end or start
                        import re
                        if re.search(r'\d{4} births', cat) and "animal" not in cat:
                            is_human = True
                            break
                        if re.search(r'\d{4} deaths', cat) and "animal" not in cat:
                            is_human = True
                            break

                    if is_human:
                        human_titles_batch.append(title)
            except Exception as e:
                print(f"Error checking categories for batch: {e}")
                pass
            
            return human_titles_batch

        # Run all batches in parallel
        tasks = [check_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        human_titles = [title for batch_result in results for title in batch_result]
        return human_titles

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
