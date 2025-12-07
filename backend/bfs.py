"""
Six Degrees of Wikipedia - Bidirectional BFS Engine

This module implements an optimized bidirectional BFS algorithm for finding
the shortest path between two Wikipedia articles, restricted to human entities.

Key Optimizations:
1. HARD TIMEOUT: asyncio.wait_for ensures search NEVER hangs
2. Smart Pagination: Early exit when enough humans found
3. VIP Fast Lane: Instant verification for famous hub nodes
4. Strict Noise Filtering: Rejects tech/product articles immediately
5. Category Caching: Eliminates redundant API calls

Author: capkimkhanh2k5
License: MIT
"""

import asyncio
import json
import logging
import os
import random
import re
import time
from collections import deque
from typing import Dict, List, Optional, Tuple, AsyncGenerator

import httpx

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Disable httpx verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# =============================================================================
# CONSTANTS
# =============================================================================

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"

# HARD TIMEOUT - The search will be force-killed after this
HARD_TIMEOUT_SECONDS = 45

# Search constraints
MAX_NODES_VISITED = 3000
BATCH_SIZE = 20
CATEGORY_BATCH_SIZE = 10
MAX_CANDIDATES_TO_CHECK = 200
MAX_DEGREE = 30
MAX_STEP_COUNT = 150
CONCURRENT_REQUESTS = 15

# Smart Pagination
MIN_HUMANS_FOR_EARLY_EXIT = 30
MAX_FETCH_BATCHES = 2  # Max 2 batches = 1000 links max

# API timeout for individual requests
API_TIMEOUT = 8.0

# Cache files
CACHE_FILE = "wiki_cache.json"
CATEGORY_CACHE_FILE = "category_cache.json"
BACKLINK_CACHE_FILE = "backlink_cache.json"

# =============================================================================
# PERSON DETECTION KEYWORDS
# =============================================================================

PERSON_POSITIVE_KEYWORDS = [
    # Modern professions
    "living people", "people from", "alumni", "players", "actors", "actresses",
    "politicians", "singers", "musicians", "writers", "directors", "scientists",
    "businesspeople", "entrepreneurs", "athletes", "journalists", "activists",
    
    # Historical figures
    "emperors", "monarchs", "khans", "sultans", "pharaohs", "tsars", "czars",
    "kings", "queens", "princes", "princesses", "dukes", "counts", "barons",
    "generals", "commanders", "admirals", "marshals", "warlords",
    "conquerors", "rulers", "regents", "caliphs", "popes", "patriarchs",
    
    # Scholars
    "philosophers", "theologians", "historians", "mathematicians", "inventors",
]

# STRICT NOISE FILTERING - prevents getting stuck on tech/product pages
PERSON_NEGATIVE_KEYWORDS = [
    # Animals
    "animal", "horse", "racehorse", "dog", "cat breed", "species",
    # Fictional
    "fictional", "character", "mythology", "mythological",
    # Organizations
    "band", "musical group", "company", "organization", "corporation",
    "companies", "inc.", "llc", "ltd",
    # Media
    "film", "movie", "song", "album", "book", "novel", "game",
    # Places
    "place", "city", "country", "river", "mountain", "building",
    # Events & Polities
    "event", "battle", "war", "treaty", "conference",
    "dynasty", "empire", "kingdom",
    # TECH/PRODUCT TRAPS (prevents iPhone, Apple Inc., etc.)
    "(pda)", "(software)", "(hardware)", "(operating system)",
    "computer", "device", "vehicle", "ship", "aircraft", 
    "product", "series", "video game", "programming language",
    "technology", "software", "hardware", "smartphone", "tablet",
    "operating system", "application", "app store", "website",
]

PERSON_EXCEPTION_KEYWORDS = ["activist", "trainer", "owner", "engineer", "developer", "founder"]

# META PAGE PATTERNS - immediate rejection in heuristic filter
META_PAGE_PATTERNS = [
    "list of", "category:", "template:", "portal:", "help:", "wikipedia:", "file:",
    "user:", "talk:", "special:", "mediawiki:", "draft:", "timedtext:", "module:",
    "disambiguation", "timeline of", "history of", "geography of", "culture of",
    "economy of", "politics of", "government of", "military of",
    # Tech article patterns
    "(software)", "(operating system)", "(programming", "(computer", "(app)",
    "(company)", "(device)", "(product)", "(video game)",
]

# =============================================================================
# VIP FAST LANE - Famous people (instant 0ms verification)
# =============================================================================

VIP_ALLOWLIST = {
    # World Leaders
    "Donald Trump", "Joe Biden", "Barack Obama", "George W. Bush", "Bill Clinton",
    "Hillary Clinton", "Vladimir Putin", "Xi Jinping", "Angela Merkel", "Emmanuel Macron",
    "Boris Johnson", "Narendra Modi", "Justin Trudeau", "Benjamin Netanyahu",
    
    # Historical Leaders
    "Genghis Khan", "Kublai Khan", "Alexander the Great", "Julius Caesar", "Augustus",
    "Napoleon Bonaparte", "Adolf Hitler", "Joseph Stalin", "Winston Churchill", 
    "Franklin D. Roosevelt", "Queen Victoria", "Queen Elizabeth II", "King Charles III",
    "Cleopatra", "Abraham Lincoln", "George Washington", "Thomas Jefferson",
    
    # Revolutionary Figures
    "Mahatma Gandhi", "Nelson Mandela", "Martin Luther King Jr.", "Che Guevara",
    "Ho Chi Minh", "Mao Zedong", "Vladimir Lenin", "Karl Marx",
    
    # Tech Moguls
    "Elon Musk", "Jeff Bezos", "Bill Gates", "Steve Jobs", "Mark Zuckerberg",
    "Warren Buffett", "Larry Page", "Sergey Brin", "Tim Cook", "Satya Nadella",
    "Steve Wozniak", "Larry Ellison", "Jack Dorsey",
    
    # Scientists
    "Albert Einstein", "Isaac Newton", "Stephen Hawking", "Nikola Tesla", 
    "Thomas Edison", "Marie Curie", "Charles Darwin", "Galileo Galilei",
    "Leonardo da Vinci", "Aristotle", "Plato", "Alan Turing",
    
    # Entertainment
    "Michael Jackson", "Elvis Presley", "Madonna", "Taylor Swift", "Beyoncé",
    "Leonardo DiCaprio", "Tom Hanks", "Brad Pitt", "Angelina Jolie",
    "Kanye West", "Oprah Winfrey",
    
    # Sports
    "Michael Jordan", "LeBron James", "Cristiano Ronaldo", "Lionel Messi",
    "Muhammad Ali", "Tiger Woods", "Serena Williams",
}

# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

_page_cache: Dict[str, Tuple[str, List[str]]] = {}
_category_cache: Dict[str, bool] = {}
_backlink_cache: Dict[str, List[str]] = {}


def load_cache() -> None:
    """Load all caches from disk."""
    global _page_cache, _category_cache, _backlink_cache
    
    for cache_file, cache_ref, name in [
        (CACHE_FILE, "_page_cache", "page"),
        (CATEGORY_CACHE_FILE, "_category_cache", "category"),
        (BACKLINK_CACHE_FILE, "_backlink_cache", "backlink"),
    ]:
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if name == "page":
                        _page_cache.update(data)
                    elif name == "category":
                        _category_cache.update(data)
                    else:
                        _backlink_cache.update(data)
                    logger.info(f"Loaded {len(data)} {name} cache entries")
            except Exception as e:
                logger.warning(f"Failed to load {name} cache: {e}")


def save_cache() -> None:
    """Save all caches to disk."""
    for cache_file, data, name in [
        (CACHE_FILE, _page_cache, "page"),
        (CATEGORY_CACHE_FILE, _category_cache, "category"),
        (BACKLINK_CACHE_FILE, _backlink_cache, "backlink"),
    ]:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save {name} cache: {e}")


load_cache()


# =============================================================================
# BIDIRECTIONAL BFS ENGINE
# =============================================================================

class BidirectionalBFS:
    """
    Bidirectional BFS with HARD TIMEOUT guarantee.
    The search will NEVER hang - it's force-killed after HARD_TIMEOUT_SECONDS.
    """
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        self.start_page: Optional[str] = None
        self.end_page: Optional[str] = None
        self.queue_f: Optional[deque] = None
        self.queue_b: Optional[deque] = None
        self.parent_f: Optional[Dict[str, Optional[str]]] = None
        self.parent_b: Optional[Dict[str, Optional[str]]] = None
        self.step_count: int = 0
        self.start_time: float = 0

    def _reconstruct_path(
        self, node: str, parent_map: Dict[str, Optional[str]], reverse: bool = False
    ) -> List[str]:
        """Reconstruct path from parent pointers."""
        path = []
        current = node
        while current is not None:
            path.append(current)
            current = parent_map.get(current)
        return path if reverse else path[::-1]

    async def _search_impl(self) -> AsyncGenerator[str, None]:
        """Internal search implementation."""
        self.start_time = time.time()
        
        # Initialize queues
        self.queue_f = deque([self.start_page])
        self.parent_f = {self.start_page: None}
        self.queue_b = deque([self.end_page])
        self.parent_b = {self.end_page: None}
        self.step_count = 0
        
        limits = httpx.Limits(max_keepalive_connections=CONCURRENT_REQUESTS, max_connections=30)
        
        async with httpx.AsyncClient(limits=limits, timeout=API_TIMEOUT) as client:
            self.client = client
            
            yield json.dumps({
                "status": "info",
                "message": f"Searching: {self.start_page} <-> {self.end_page}"
            })

            while self.queue_f and self.queue_b:
                elapsed = time.time() - self.start_time
                total_visited = len(self.parent_f) + len(self.parent_b)
                
                # Soft timeout check (backup)
                if elapsed > HARD_TIMEOUT_SECONDS - 5:
                    save_cache()
                    yield json.dumps({"status": "error", "message": "Approaching timeout limit."})
                    return

                if total_visited > MAX_NODES_VISITED:
                    save_cache()
                    yield json.dumps({"status": "error", "message": f"Node limit exceeded ({MAX_NODES_VISITED})."})
                    return

                self.step_count += 1
                
                # Expand smaller frontier
                if len(self.queue_f) <= len(self.queue_b):
                    direction, queue = "forward", self.queue_f
                    parent_own, parent_other = self.parent_f, self.parent_b
                else:
                    direction, queue = "backward", self.queue_b
                    parent_own, parent_other = self.parent_b, self.parent_f

                level_nodes = [queue.popleft() for _ in range(min(len(queue), BATCH_SIZE))]
                
                yield json.dumps({
                    "status": "exploring",
                    "direction": direction,
                    "nodes": level_nodes,
                    "stats": {"visited": total_visited, "time": round(elapsed, 1)}
                })
                
                # Process nodes with timeout per batch
                try:
                    tasks = [self._process_node(node, direction) for node in level_nodes]
                    results = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=15.0  # 15s max per batch
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Batch timeout for {level_nodes}")
                    continue
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception) or not result:
                        continue
                        
                    for child in result["children"]:
                        if child in parent_own:
                            continue
                        parent_own[child] = result["node"]
                        queue.append(child)
                        
                        if child in parent_other:
                            path_f = self._reconstruct_path(child, self.parent_f)
                            path_b = self._reconstruct_path(child, self.parent_b, reverse=True)
                            full_path = path_f[:-1] + path_b
                            save_cache()
                            yield json.dumps({"status": "finished", "path": full_path})
                            return

                if self.step_count > MAX_STEP_COUNT:
                    save_cache()
                    yield json.dumps({"status": "error", "message": "Step limit exceeded."})
                    return
            
            save_cache()
            yield json.dumps({"status": "not_found", "message": "No path found."})

    async def search(self, start_node: str, end_node: str) -> AsyncGenerator[str, None]:
        """
        Execute search with HARD TIMEOUT guarantee.
        Uses asyncio.wait_for to ensure the search NEVER hangs.
        """
        self.start_page = start_node
        self.end_page = end_node
        
        try:
            # Collect all messages with hard timeout
            async def collect_results():
                results = []
                async for msg in self._search_impl():
                    results.append(msg)
                return results
            
            try:
                messages = await asyncio.wait_for(collect_results(), timeout=HARD_TIMEOUT_SECONDS)
                for msg in messages:
                    yield msg
            except asyncio.TimeoutError:
                save_cache()
                yield json.dumps({
                    "status": "error",
                    "message": f"HARD TIMEOUT: Search force-killed after {HARD_TIMEOUT_SECONDS}s"
                })
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            yield json.dumps({"status": "error", "message": str(e)})

    async def _process_node(self, current_node: str, direction: str) -> Optional[Dict]:
        """Process a single node with timeout."""
        try:
            async with self.semaphore:
                if direction == "forward":
                    _, candidates = await asyncio.wait_for(
                        self._get_page_data(current_node), timeout=10.0
                    )
                else:
                    candidates = await asyncio.wait_for(
                        self._get_backlinks(current_node), timeout=10.0
                    )

                filtered = self._heuristic_filter(candidates)
                random.shuffle(filtered)
                
                humans = await asyncio.wait_for(
                    self._batch_check_categories(filtered[:MAX_CANDIDATES_TO_CHECK]),
                    timeout=15.0
                )
                
                logger.info(f"{current_node} ({direction}): {len(candidates)} → {len(filtered)} → {len(humans)} humans")
                
                return {"node": current_node, "children": humans[:MAX_DEGREE]}
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing {current_node}")
            return None
        except Exception as e:
            logger.error(f"Error processing {current_node}: {e}")
            return None

    async def _batch_check_categories(self, titles: List[str]) -> List[str]:
        """Check if articles are about humans. Uses VIP + Cache + API."""
        global _category_cache
        
        if not titles:
            return []
        
        # VIP Fast Lane
        vip = [t for t in titles if t in VIP_ALLOWLIST]
        remaining = [t for t in titles if t not in VIP_ALLOWLIST]
        
        # Cache
        cached = [t for t in remaining if _category_cache.get(t, False)]
        uncached = [t for t in remaining if t not in _category_cache]
        
        if not uncached:
            return vip + cached
        
        # API batch check
        batches = [uncached[i:i+CATEGORY_BATCH_SIZE] for i in range(0, len(uncached), CATEGORY_BATCH_SIZE)]
        
        async def check_batch(batch: List[str]) -> List[str]:
            try:
                async with self.semaphore:
                    resp = await self.client.get(
                        WIKIPEDIA_API_URL,
                        params={
                            "action": "query", "format": "json",
                            "titles": "|".join(batch),
                            "prop": "categories", "cllimit": "max", "redirects": 1
                        },
                        headers={"User-Agent": USER_AGENT}
                    )
                
                if resp.status_code != 200:
                    return []
                
                humans = []
                for page in resp.json().get("query", {}).get("pages", {}).values():
                    title = page.get("title")
                    if "missing" in page:
                        _category_cache[title] = False
                        continue
                    
                    cats = [c["title"].lower() for c in page.get("categories", [])]
                    clean = [c[9:] if c.startswith("category:") else c for c in cats]
                    
                    is_human = self._is_human(cats, clean)
                    _category_cache[title] = is_human
                    if is_human:
                        humans.append(title)
                
                return humans
            except Exception as e:
                logger.error(f"Batch error: {e}")
                return []
        
        results = await asyncio.gather(*[check_batch(b) for b in batches], return_exceptions=True)
        api_humans = [h for r in results if not isinstance(r, Exception) for h in r]
        
        return vip + cached + api_humans

    def _is_human(self, categories: List[str], clean_categories: List[str]) -> bool:
        """Determine if article is about a human."""
        # Negative filter
        for cat in clean_categories:
            if any(neg in cat for neg in PERSON_NEGATIVE_KEYWORDS):
                if not any(exc in cat for exc in PERSON_EXCEPTION_KEYWORDS):
                    return False
        
        # Positive filter
        for cat in categories:
            if any(kw in cat for kw in PERSON_POSITIVE_KEYWORDS):
                return True
            if re.search(r'\d{4} births', cat) and "animal" not in cat:
                return True
            if re.search(r'\d{4} deaths', cat) and "animal" not in cat:
                return True
            if re.search(r'\d{1,2}(st|nd|rd|th)-century', cat):
                if any(r in cat for r in ["rulers", "people", "monarchs", "leaders"]):
                    return True
        return False

    async def _get_page_data(self, title: str) -> Tuple[str, List[str]]:
        """
        Fetch page data with SMART PAGINATION.
        Early exits when >= 30 potential humans found.
        Max 2 batches (1000 links).
        """
        global _page_cache
        
        if title in _page_cache:
            return _page_cache[title]
        
        headers = {"User-Agent": USER_AGENT}
        
        try:
            # Fetch text
            resp = await self.client.get(
                WIKIPEDIA_API_URL,
                params={"action": "query", "format": "json", "titles": title,
                        "prop": "extracts", "explaintext": 1, "exintro": 1},
                headers=headers
            )
            text = ""
            for p in resp.json().get("query", {}).get("pages", {}).values():
                text = p.get("extract", "")
            
            # SMART PAGINATION for links
            params = {"action": "query", "format": "json", "titles": title,
                      "prop": "links", "plnamespace": 0, "pllimit": "max"}
            
            all_links = []
            potential_humans = 0
            
            for batch_num in range(MAX_FETCH_BATCHES):
                resp = await self.client.get(WIKIPEDIA_API_URL, params=params, headers=headers)
                data = resp.json()
                
                new_links = []
                for p in data.get("query", {}).get("pages", {}).values():
                    if "links" in p:
                        new_links = [l["title"] for l in p["links"]]
                
                all_links.extend(new_links)
                
                # EARLY EXIT: Check if we have enough potential humans
                filtered = self._heuristic_filter(new_links)
                potential_humans += len(filtered)
                
                if potential_humans >= MIN_HUMANS_FOR_EARLY_EXIT:
                    break  # We have enough, no need for more batches
                
                if "continue" not in data:
                    break
                params.update(data["continue"])
            
            result = (text, all_links)
            _page_cache[title] = result
            return result
            
        except Exception as e:
            logger.error(f"Error fetching {title}: {e}")
            return "", []

    async def _get_backlinks(self, title: str) -> List[str]:
        """Fetch backlinks (single batch, max 500, no pagination)."""
        global _backlink_cache
        
        if title in _backlink_cache:
            return _backlink_cache[title]
        
        try:
            resp = await self.client.get(
                WIKIPEDIA_API_URL,
                params={"action": "query", "format": "json",
                        "list": "backlinks", "bltitle": title,
                        "blnamespace": 0, "bllimit": "max"},
                headers={"User-Agent": USER_AGENT}
            )
            
            backlinks = []
            data = resp.json()
            if "backlinks" in data.get("query", {}):
                backlinks = [b["title"] for b in data["query"]["backlinks"]]
            
            _backlink_cache[title] = backlinks
            return backlinks
            
        except Exception as e:
            logger.error(f"Error fetching backlinks for {title}: {e}")
            return []

    def _heuristic_filter(self, candidates: List[str]) -> List[str]:
        """Quick filter to remove non-person articles."""
        filtered = []
        for c in candidates:
            if not c or c[0].isdigit():
                continue
            lower = c.lower()
            if c.startswith("List of"):
                continue
            if any(p in lower for p in META_PAGE_PATTERNS):
                continue
            filtered.append(c)
        return filtered


# =============================================================================
# PUBLIC API
# =============================================================================

async def find_shortest_path(start_page: str, end_page: str) -> AsyncGenerator[str, None]:
    """Main entry point with HARD TIMEOUT guarantee."""
    searcher = BidirectionalBFS()
    async for msg in searcher.search(start_page, end_page):
        yield msg
