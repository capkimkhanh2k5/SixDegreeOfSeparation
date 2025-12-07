import asyncio
import json
import httpx
from collections import deque
from typing import List, Set, Dict, Optional, AsyncGenerator, Tuple
from .llm_client import verify_candidates_with_llm
import os
import re
import random

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

# ============================================================
# PERSISTENT CACHE IMPLEMENTATION (Optimized for Extreme Cases)
# ============================================================
CACHE_FILE = "wiki_cache.json"
CATEGORY_CACHE_FILE = "category_cache.json"
BACKLINK_CACHE_FILE = "backlink_cache.json"

_page_cache = {}
_category_cache = {}  # title -> bool (is_human) - NEW: Prevents redundant API calls
_backlink_cache = {}  # title -> List[str] - NEW: Cache backlinks

def load_cache():
    """Load all caches from disk."""
    global _page_cache, _category_cache, _backlink_cache
    
    # Load page cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                _page_cache = json.load(f)
            print(f"[CACHE] Loaded {len(_page_cache)} page items.")
        except Exception as e:
            print(f"[CACHE] Failed to load page cache: {e}")
    
    # Load category cache
    if os.path.exists(CATEGORY_CACHE_FILE):
        try:
            with open(CATEGORY_CACHE_FILE, 'r') as f:
                _category_cache = json.load(f)
            print(f"[CACHE] Loaded {len(_category_cache)} category items.")
        except Exception as e:
            print(f"[CACHE] Failed to load category cache: {e}")
    
    # Load backlink cache
    if os.path.exists(BACKLINK_CACHE_FILE):
        try:
            with open(BACKLINK_CACHE_FILE, 'r') as f:
                _backlink_cache = json.load(f)
            print(f"[CACHE] Loaded {len(_backlink_cache)} backlink items.")
        except Exception as e:
            print(f"[CACHE] Failed to load backlink cache: {e}")

def save_cache():
    """Save all caches to disk."""
    global _page_cache, _category_cache, _backlink_cache
    
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(_page_cache, f)
    except Exception as e:
        print(f"[CACHE] Failed to save page cache: {e}")
    
    try:
        with open(CATEGORY_CACHE_FILE, 'w') as f:
            json.dump(_category_cache, f)
    except Exception as e:
        print(f"[CACHE] Failed to save category cache: {e}")
    
    try:
        with open(BACKLINK_CACHE_FILE, 'w') as f:
            json.dump(_backlink_cache, f)
    except Exception as e:
        print(f"[CACHE] Failed to save backlink cache: {e}")

# Load cache on module import
load_cache()

# ============================================================
# OPTIMIZED HISTORICAL FIGURE KEYWORDS
# ============================================================
# Positive keywords that indicate a human (expanded for historical figures)
PERSON_POSITIVE_KEYWORDS = [
    # Modern professions
    "living people", "people from", "alumni", "players", "actors", "actresses",
    "politicians", "singers", "musicians", "writers", "directors", "scientists",
    "businesspeople", "entrepreneurs", "athletes", "journalists", "activists",
    
    # Historical figures (NEW - Critical for Genghis Khan case)
    "emperors", "monarchs", "khans", "sultans", "pharaohs", "tsars", "czars",
    "kings", "queens", "princes", "princesses", "dukes", "counts", "barons",
    "generals", "commanders", "admirals", "marshals", "warlords",
    "conquerors", "rulers", "regents", "caliphs", "popes", "patriarchs",
    
    # Scholars and thinkers
    "philosophers", "theologians", "historians", "mathematicians", "inventors",
    
    # Birth/death year patterns handled separately
]

# Negative keywords (exclude non-humans)
PERSON_NEGATIVE_KEYWORDS = [
    "animal", "horse", "racehorse", "dog", "cat breed", "species",
    "fictional", "character", "mythology", "mythological",
    "band", "musical group", "company", "organization", "corporation",
    "film", "movie", "song", "album", "book", "novel", "game",
    "place", "city", "country", "river", "mountain", "building",
    "event", "battle", "war", "treaty", "conference",  # Exclude events
    "dynasty", "empire", "kingdom",  # Exclude polities
]


class BidirectionalLevelBasedSearch:
    """
    Optimized Bidirectional BFS for finding paths between Wikipedia articles.
    
    Optimizations applied:
    1. Category caching to avoid redundant API calls
    2. Backlink caching for popular targets
    3. Memory-efficient visited sets (parent pointers only)
    4. Historical figure detection for ancient personalities
    5. Robust exception handling
    """
    
    def __init__(self):
        self.client = None
        self.start_page = None
        self.end_page = None
        self.MAX_DEGREE = 30
        self.MAX_DEPTH = 10
        self.step_count = 0
        self.semaphore = asyncio.Semaphore(20)  # Limit concurrent requests
        
        # Queues: (node, path_list)
        self.queue_f = None
        self.queue_b = None
        
        # OPTIMIZATION: Memory-efficient visited sets
        # Store {child: parent} instead of {child: [full, path, list]}
        # Path is reconstructed on demand when intersection is found
        self.parent_f = None  # Forward: child -> parent
        self.parent_b = None  # Backward: child -> parent

    def _reconstruct_path(self, node: str, parent_map: Dict[str, Optional[str]], reverse: bool = False) -> List[str]:
        """Reconstruct path from parent pointers."""
        path = []
        current = node
        while current is not None:
            path.append(current)
            current = parent_map.get(current)
        
        if reverse:
            return path
        return path[::-1]

    async def search(self, start_node: str, end_node: str) -> AsyncGenerator[str, None]:
        """
        Executes Bidirectional BFS with optimized memory usage.
        Yields JSON status messages.
        """
        self.start_page = start_node
        self.end_page = end_node
        
        import time
        start_time = time.time()
        TIMEOUT = 60  # seconds
        MAX_NODES_VISITED = 2000
        
        # OPTIMIZATION: Use parent pointers instead of full paths
        self.queue_f = deque([self.start_page])
        self.parent_f = {self.start_page: None}  # Root has no parent
        
        self.queue_b = deque([self.end_page])
        self.parent_b = {self.end_page: None}  # Root has no parent
        
        self.step_count = 0
        
        # Configure client with higher concurrency limits
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
        async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
            self.client = client
            
            yield json.dumps({
                "status": "info", 
                "message": f"Initializing Bidirectional Search: {self.start_page} <-> {self.end_page}"
            })

            while self.queue_f and self.queue_b:
                # Safety Checks
                elapsed = time.time() - start_time
                if elapsed > TIMEOUT:
                    save_cache()  # Save progress before timeout
                    yield json.dumps({
                        "status": "error", 
                        "message": f"Search timed out after {TIMEOUT} seconds."
                    })
                    return

                total_visited = len(self.parent_f) + len(self.parent_b)
                if total_visited > MAX_NODES_VISITED:
                    save_cache()
                    yield json.dumps({
                        "status": "error", 
                        "message": f"Search limit exceeded ({MAX_NODES_VISITED} nodes)."
                    })
                    return

                self.step_count += 1
                
                # Expand the smaller frontier (BFS optimization)
                if len(self.queue_f) <= len(self.queue_b):
                    direction = "forward"
                    queue = self.queue_f
                    parent_own = self.parent_f
                    parent_other = self.parent_b
                else:
                    direction = "backward"
                    queue = self.queue_b
                    parent_own = self.parent_b
                    parent_other = self.parent_f

                # Process one level (batch for concurrency)
                batch_size = 20
                level_nodes = []
                for _ in range(min(len(queue), batch_size)):
                    level_nodes.append(queue.popleft())
                
                # Notify UI
                yield json.dumps({
                    "status": "exploring", 
                    "direction": direction, 
                    "nodes": level_nodes,
                    "stats": {
                        "visited": total_visited,
                        "queue_f": len(self.queue_f),
                        "queue_b": len(self.queue_b),
                        "time": round(elapsed, 1)
                    }
                })
                
                # OPTIMIZATION: Robust exception handling with return_exceptions
                tasks = [
                    self.process_node(node, direction) 
                    for node in level_nodes
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    # Handle exceptions gracefully
                    if isinstance(result, Exception):
                        print(f"[ERROR] Task failed for node: {level_nodes[i]}: {result}")
                        continue
                    if not result:
                        continue
                        
                    current_node, children = result["node"], result["children"]
                    
                    for child in children:
                        if child in parent_own:
                            continue  # Already visited from this direction
                            
                        parent_own[child] = current_node  # Store parent pointer
                        queue.append(child)
                        
                        # Check for intersection
                        if child in parent_other:
                            # Path found! Reconstruct from parent pointers
                            if direction == "forward":
                                path_f = self._reconstruct_path(child, self.parent_f)
                                path_b = self._reconstruct_path(child, self.parent_b, reverse=True)
                                full_path = path_f[:-1] + path_b  # Avoid duplicating intersection node
                            else:
                                path_f = self._reconstruct_path(child, self.parent_f)
                                path_b = self._reconstruct_path(child, self.parent_b, reverse=True)
                                full_path = path_f[:-1] + path_b
                            
                            save_cache()  # Save cache on success
                            yield json.dumps({"status": "finished", "path": full_path})
                            return

                # Depth limit check
                if self.step_count > 100:
                    save_cache()
                    yield json.dumps({
                        "status": "error", 
                        "message": "Search depth limit exceeded."
                    })
                    return
            
            save_cache()
            yield json.dumps({"status": "not_found", "message": "No path found."})

    async def process_node(self, current_node: str, direction: str) -> Optional[Dict]:
        """Process a single node and return its valid human children."""
        async with self.semaphore:
            try:
                # 1. Fetch Candidates
                if direction == "forward":
                    wiki_text, candidates = await self.get_page_data(current_node)
                else:
                    candidates = await self.get_backlinks(current_node)

                # 2. Heuristic Filter (Name-based)
                filtered_candidates = self.heuristic_filter(candidates)
                
                # Shuffle to avoid alphabetical bias
                random.shuffle(filtered_candidates)
                
                # 3. Strict Person Check (Category-based with CACHING)
                candidates_to_check = filtered_candidates[:500]
                human_candidates = await self.batch_check_categories(candidates_to_check)
                
                print(f"[DEBUG] {current_node} ({direction}): "
                      f"{len(candidates)} -> {len(filtered_candidates)} -> {len(human_candidates)} humans")

                # 4. Limit final candidates
                final_candidates = human_candidates[:self.MAX_DEGREE]
                      
                return {
                    "node": current_node,
                    "children": final_candidates,
                }
            except Exception as e:
                print(f"[ERROR] Processing node {current_node} ({direction}): {e}")
                return None
    
    async def batch_check_categories(self, titles: List[str]) -> List[str]:
        """
        Checks if titles are humans based on Wikipedia categories.
        OPTIMIZATION: Uses category cache to avoid redundant API calls.
        """
        global _category_cache
        
        if not titles:
            return []
        
        # OPTIMIZATION: Check cache first
        cached_humans = []
        uncached_titles = []
        
        for title in titles:
            if title in _category_cache:
                if _category_cache[title]:  # True = is human
                    cached_humans.append(title)
                # False = not human, skip
            else:
                uncached_titles.append(title)
        
        # If all cached, return immediately
        if not uncached_titles:
            return cached_humans
        
        # Chunk uncached into batches of 10
        chunk_size = 10
        batches = [uncached_titles[i:i+chunk_size] for i in range(0, len(uncached_titles), chunk_size)]
        
        async def check_batch(batch: List[str]) -> List[str]:
            human_titles_batch = []
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
                async with self.semaphore:
                    resp = await self.client.get(API_URL, params=params, headers=headers)
                
                if resp.status_code != 200:
                    print(f"[API] Error: Status {resp.status_code} for batch check")
                    return []
                    
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    print(f"[API] Invalid JSON response for batch check")
                    return []
                    
                pages = data.get("query", {}).get("pages", {})
                
                for _, page in pages.items():
                    title = page.get("title")
                    
                    if "missing" in page:
                        _category_cache[title] = False
                        continue
                        
                    categories = [c["title"].lower() for c in page.get("categories", [])]
                    
                    # Strip "Category:" prefix
                    clean_categories = []
                    for c in categories:
                        if c.startswith("category:"):
                            clean_categories.append(c[9:])
                        else:
                            clean_categories.append(c)
                    
                    is_human = self._check_is_human(categories, clean_categories)
                    
                    # Cache the result
                    _category_cache[title] = is_human
                    
                    if is_human:
                        human_titles_batch.append(title)
                        
            except Exception as e:
                print(f"[ERROR] Checking categories for batch: {e}")
            
            return human_titles_batch

        # Run all batches in parallel
        tasks = [check_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results (filter out exceptions)
        human_titles = []
        for result in results:
            if isinstance(result, Exception):
                print(f"[ERROR] Batch check failed: {result}")
                continue
            human_titles.extend(result)
        
        return cached_humans + human_titles
    
    def _check_is_human(self, categories: List[str], clean_categories: List[str]) -> bool:
        """
        Determine if a Wikipedia article is about a human.
        OPTIMIZATION: Expanded keywords for historical figures.
        """
        is_human = False
        is_excluded = False
        
        # 1. Negative Filters (Exclude animals, fictional, non-persons)
        for cat in clean_categories:
            if any(neg in cat for neg in PERSON_NEGATIVE_KEYWORDS):
                # Exception: human-related categories with animal terms
                # e.g., "Animal rights activists", "Horse trainers"
                if any(exc in cat for exc in ["activist", "trainer", "owner", "breeder", "rider"]):
                    continue
                is_excluded = True
                break
        
        if is_excluded:
            return False

        # 2. Positive Filters (Must match at least one)
        for cat in categories:
            # Check direct keyword matches
            for keyword in PERSON_POSITIVE_KEYWORDS:
                if keyword in cat:
                    is_human = True
                    break
            
            if is_human:
                break
            
            # Check for Year Births/Deaths (e.g., "Category:1946 births")
            if re.search(r'\d{4} births', cat) and "animal" not in cat:
                is_human = True
                break
            if re.search(r'\d{4} deaths', cat) and "animal" not in cat:
                is_human = True
                break
            
            # Check for century-based categories (e.g., "12th-century Mongol rulers")
            if re.search(r'\d{1,2}(st|nd|rd|th)-century', cat):
                # Likely historical figure if century-based
                if any(role in cat for role in ["rulers", "people", "monarchs", "leaders", "generals"]):
                    is_human = True
                    break
        
        return is_human

    async def get_page_data(self, title: str) -> Tuple[str, List[str]]:
        """Fetch page extract and links with caching."""
        global _page_cache
        
        if title in _page_cache:
            return _page_cache[title]
        
        headers = {
            "User-Agent": "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"
        }
        
        try:
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
            for _, p in pages.items():
                text = p.get("extract", "")
            
            # Parse Links (with pagination)
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
                    if len(links) > 2000:
                        break  # Safety limit
                else:
                    break
            
            result = (text, links)
            _page_cache[title] = result
            return result
            
        except Exception as e:
            print(f"[API] Error (Forward) {title}: {e}")
            return "", []

    async def get_backlinks(self, title: str) -> List[str]:
        """
        Fetch backlinks with CACHING.
        OPTIMIZATION: Cache backlinks to avoid redundant fetches for popular targets.
        """
        global _backlink_cache
        
        # Check cache
        if title in _backlink_cache:
            return _backlink_cache[title]
        
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
                    if len(backlinks) > 2000:
                        break
                else:
                    break
            
            # Cache the result
            _backlink_cache[title] = backlinks
            return backlinks
            
        except Exception as e:
            print(f"[API] Error (Backward) {title}: {e}")
            return []

    def heuristic_filter(self, candidates: List[str]) -> List[str]:
        """Filter out Wikipedia meta-pages and obvious non-person articles."""
        filtered = []
        
        exclude_keywords = [
            "list of", "category:", "template:", "portal:", "help:", "wikipedia:", "file:",
            "user:", "talk:", "special:", "mediawiki:", "draft:", "timedtext:", "module:",
            "disambiguation", "timeline of", "history of", "geography of", "culture of",
            "economy of", "politics of", "government of", "military of",
        ]
        
        for c in candidates:
            c_lower = c.lower()
            
            # Skip years/dates
            if c[0].isdigit():
                continue
            
            # Skip "List of..." articles
            if c.startswith("List of"):
                continue
            
            # Check exclusion keywords
            is_excluded = False
            for k in exclude_keywords:
                if k in c_lower:
                    is_excluded = True
                    break
            
            if not is_excluded:
                filtered.append(c)
                
        return filtered


# Wrapper for main.py (streaming interface)
async def find_shortest_path(start_page: str, end_page: str):
    """
    Main entry point for the BFS search.
    Yields JSON messages for streaming to frontend.
    """
    searcher = BidirectionalLevelBasedSearch()
    async for msg in searcher.search(start_page, end_page):
        yield msg
