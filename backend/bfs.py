"""
Six Degrees of Wikipedia - Bidirectional BFS Engine

This module implements an optimized bidirectional BFS algorithm for finding
the shortest path between two Wikipedia articles, restricted to human entities.

Key Optimizations:
1. Bidirectional Search: O(b^(d/2)) instead of O(b^d) complexity
2. Category Caching: Eliminates redundant Wikipedia API calls
3. Parent-Pointer Path Reconstruction: ~8x memory reduction
4. Smart Pagination: Early exit when enough human candidates found
5. VIP Fast Lane: Instant verification for famous hub nodes
6. Historical Figure Detection: Supports ancient personalities

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

# Disable httpx verbose HTTP request logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# =============================================================================
# CONSTANTS
# =============================================================================

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"

# Search constraints (tuned for performance)
TIMEOUT_SECONDS = 45
MAX_NODES_VISITED = 3000
BATCH_SIZE = 20
CATEGORY_BATCH_SIZE = 10
MAX_CANDIDATES_TO_CHECK = 300
MAX_DEGREE = 30
MAX_STEP_COUNT = 100
CONCURRENT_REQUESTS = 20

# Smart Pagination settings
MIN_HUMANS_FOR_EARLY_EXIT = 30  # Stop fetching when we have enough humans
MAX_FETCH_BATCHES = 3  # Max pagination batches (3 x 500 = 1500 links max)

# Cache file paths
CACHE_FILE = "wiki_cache.json"
CATEGORY_CACHE_FILE = "category_cache.json"
BACKLINK_CACHE_FILE = "backlink_cache.json"

# =============================================================================
# PERSON DETECTION KEYWORDS
# =============================================================================

# Keywords indicating a Wikipedia article is about a human
PERSON_POSITIVE_KEYWORDS = [
    # Modern professions
    "living people", "people from", "alumni", "players", "actors", "actresses",
    "politicians", "singers", "musicians", "writers", "directors", "scientists",
    "businesspeople", "entrepreneurs", "athletes", "journalists", "activists",
    
    # Historical figures (critical for Genghis Khan → Elon Musk case)
    "emperors", "monarchs", "khans", "sultans", "pharaohs", "tsars", "czars",
    "kings", "queens", "princes", "princesses", "dukes", "counts", "barons",
    "generals", "commanders", "admirals", "marshals", "warlords",
    "conquerors", "rulers", "regents", "caliphs", "popes", "patriarchs",
    
    # Scholars and thinkers
    "philosophers", "theologians", "historians", "mathematicians", "inventors",
]

# Keywords indicating non-human entities to exclude
PERSON_NEGATIVE_KEYWORDS = [
    # Animals
    "animal", "horse", "racehorse", "dog", "cat breed", "species",
    # Fictional
    "fictional", "character", "mythology", "mythological",
    # Organizations
    "band", "musical group", "company", "organization", "corporation",
    # Media
    "film", "movie", "song", "album", "book", "novel", "game",
    # Places
    "place", "city", "country", "river", "mountain", "building",
    # Events & Polities
    "event", "battle", "war", "treaty", "conference",
    "dynasty", "empire", "kingdom",
    # Tech/Gadget noise (NEW - prevents stuck on tech articles)
    "(pda)", "(software)", "computer", "device", "vehicle", "ship", 
    "aircraft", "product", "series", "video game", "programming",
    "operating system", "technology", "software", "hardware",
]

# Exceptions: categories containing these words are about humans despite negative keywords
PERSON_EXCEPTION_KEYWORDS = ["activist", "trainer", "owner", "breeder", "rider", "engineer", "developer"]

# Wikipedia meta-page patterns to filter out
META_PAGE_PATTERNS = [
    "list of", "category:", "template:", "portal:", "help:", "wikipedia:", "file:",
    "user:", "talk:", "special:", "mediawiki:", "draft:", "timedtext:", "module:",
    "disambiguation", "timeline of", "history of", "geography of", "culture of",
    "economy of", "politics of", "government of", "military of",
    # Tech article patterns
    "(software)", "(operating system)", "(programming", "(computer",
]

# =============================================================================
# VIP FAST LANE - Famous Hub Nodes (0ms verification)
# =============================================================================

VIP_ALLOWLIST = {
    # Modern World Leaders
    "Donald Trump", "Joe Biden", "Barack Obama", "George W. Bush", "Bill Clinton",
    "Hillary Clinton", "Vladimir Putin", "Xi Jinping", "Angela Merkel", "Emmanuel Macron",
    "Boris Johnson", "Narendra Modi", "Shinzo Abe", "Justin Trudeau", "Benjamin Netanyahu",
    
    # Historical Leaders & Monarchs
    "Genghis Khan", "Kublai Khan", "Alexander the Great", "Julius Caesar", "Augustus",
    "Napoleon Bonaparte", "Adolf Hitler", "Joseph Stalin", "Winston Churchill", "Franklin D. Roosevelt",
    "Queen Victoria", "Queen Elizabeth II", "King Charles III", "Henry VIII of England",
    "Louis XIV", "Peter the Great", "Catherine the Great", "Cleopatra", "Ramesses II",
    
    # Revolutionary Figures
    "George Washington", "Abraham Lincoln", "Thomas Jefferson", "Mahatma Gandhi",
    "Nelson Mandela", "Martin Luther King Jr.", "Che Guevara", "Ho Chi Minh",
    "Mao Zedong", "Vladimir Lenin", "Karl Marx", "Friedrich Engels",
    
    # Tech & Business Moguls
    "Elon Musk", "Jeff Bezos", "Bill Gates", "Steve Jobs", "Mark Zuckerberg",
    "Warren Buffett", "Larry Page", "Sergey Brin", "Tim Cook", "Satya Nadella",
    "Jack Ma", "Richard Branson", "Oprah Winfrey",
    
    # Scientists & Inventors
    "Albert Einstein", "Isaac Newton", "Stephen Hawking", "Nikola Tesla", "Thomas Edison",
    "Marie Curie", "Charles Darwin", "Galileo Galilei", "Leonardo da Vinci", "Aristotle",
    "Plato", "Socrates", "Archimedes", "Alan Turing", "Richard Feynman",
    
    # Entertainment & Culture
    "Michael Jackson", "Elvis Presley", "Madonna", "Taylor Swift",
    "Beyoncé", "Lady Gaga", "Kanye West", "Drake", "Rihanna",
    "Leonardo DiCaprio", "Tom Hanks", "Meryl Streep", "Brad Pitt", "Angelina Jolie",
    "Johnny Depp", "Will Smith", "Dwayne Johnson", "Marilyn Monroe", "Audrey Hepburn",
    
    # Sports Legends
    "Michael Jordan", "LeBron James", "Cristiano Ronaldo", "Lionel Messi", "Serena Williams",
    "Roger Federer", "Muhammad Ali", "Mike Tyson", "Usain Bolt", "Tiger Woods",
    
    # Religious & Philosophical Figures
    "Jesus", "Muhammad", "Buddha", "Pope Francis", "Dalai Lama",
    "Confucius", "Moses", "Saint Paul", "Martin Luther",
}

# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

_page_cache: Dict[str, Tuple[str, List[str]]] = {}
_category_cache: Dict[str, bool] = {}
_backlink_cache: Dict[str, List[str]] = {}


def load_cache() -> None:
    """Load all caches from disk on module initialization."""
    global _page_cache, _category_cache, _backlink_cache
    
    for cache_file, cache_name in [
        (CACHE_FILE, "page"),
        (CATEGORY_CACHE_FILE, "category"),
        (BACKLINK_CACHE_FILE, "backlink"),
    ]:
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if cache_name == "page":
                        _page_cache.update(loaded)
                    elif cache_name == "category":
                        _category_cache.update(loaded)
                    elif cache_name == "backlink":
                        _backlink_cache.update(loaded)
                    logger.info(f"Loaded {len(loaded)} {cache_name} cache entries")
            except Exception as e:
                logger.warning(f"Failed to load {cache_name} cache: {e}")


def save_cache() -> None:
    """Persist all caches to disk."""
    for cache_file, cache_data, name in [
        (CACHE_FILE, _page_cache, "page"),
        (CATEGORY_CACHE_FILE, _category_cache, "category"),
        (BACKLINK_CACHE_FILE, _backlink_cache, "backlink"),
    ]:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.warning(f"Failed to save {name} cache: {e}")


# Load cache on module import
load_cache()


# =============================================================================
# BIDIRECTIONAL BFS SEARCH ENGINE
# =============================================================================

class BidirectionalBFS:
    """
    Bidirectional Breadth-First Search for finding shortest paths between
    Wikipedia articles, restricted to human entities only.
    """
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        
        # Search state
        self.start_page: Optional[str] = None
        self.end_page: Optional[str] = None
        self.queue_f: Optional[deque] = None
        self.queue_b: Optional[deque] = None
        self.parent_f: Optional[Dict[str, Optional[str]]] = None
        self.parent_b: Optional[Dict[str, Optional[str]]] = None
        self.step_count: int = 0

    def _reconstruct_path(
        self, 
        node: str, 
        parent_map: Dict[str, Optional[str]], 
        reverse: bool = False
    ) -> List[str]:
        """Reconstruct path from parent pointers."""
        path = []
        current = node
        while current is not None:
            path.append(current)
            current = parent_map.get(current)
        return path if reverse else path[::-1]

    async def search(
        self, 
        start_node: str, 
        end_node: str
    ) -> AsyncGenerator[str, None]:
        """
        Execute bidirectional BFS search.
        Yields JSON status messages for real-time progress updates.
        """
        self.start_page = start_node
        self.end_page = end_node
        
        start_time = time.time()
        
        # Initialize bidirectional queues and parent maps
        self.queue_f = deque([self.start_page])
        self.parent_f = {self.start_page: None}
        
        self.queue_b = deque([self.end_page])
        self.parent_b = {self.end_page: None}
        
        self.step_count = 0
        
        # Configure HTTP client
        limits = httpx.Limits(
            max_keepalive_connections=CONCURRENT_REQUESTS,
            max_connections=CONCURRENT_REQUESTS + 10
        )
        
        async with httpx.AsyncClient(limits=limits, timeout=15.0) as client:
            self.client = client
            
            yield json.dumps({
                "status": "info",
                "message": f"Initializing Bidirectional Search: {self.start_page} <-> {self.end_page}"
            })

            while self.queue_f and self.queue_b:
                elapsed = time.time() - start_time
                
                # Safety: timeout
                if elapsed > TIMEOUT_SECONDS:
                    save_cache()
                    yield json.dumps({
                        "status": "error",
                        "message": f"Search timed out after {TIMEOUT_SECONDS} seconds."
                    })
                    return

                # Safety: max nodes
                total_visited = len(self.parent_f) + len(self.parent_b)
                if total_visited > MAX_NODES_VISITED:
                    save_cache()
                    yield json.dumps({
                        "status": "error",
                        "message": f"Search limit exceeded ({MAX_NODES_VISITED} nodes)."
                    })
                    return

                self.step_count += 1
                
                # Expand smaller frontier
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

                # Process nodes in batches
                level_nodes = []
                for _ in range(min(len(queue), BATCH_SIZE)):
                    level_nodes.append(queue.popleft())
                
                # Emit progress
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
                
                # Process all nodes concurrently
                tasks = [self._process_node(node, direction) for node in level_nodes]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Task failed for {level_nodes[i]}: {result}")
                        continue
                    if not result:
                        continue
                        
                    current_node = result["node"]
                    children = result["children"]
                    
                    for child in children:
                        if child in parent_own:
                            continue
                            
                        parent_own[child] = current_node
                        queue.append(child)
                        
                        # Check for intersection
                        if child in parent_other:
                            path_f = self._reconstruct_path(child, self.parent_f)
                            path_b = self._reconstruct_path(child, self.parent_b, reverse=True)
                            full_path = path_f[:-1] + path_b
                            
                            save_cache()
                            yield json.dumps({"status": "finished", "path": full_path})
                            return

                # Depth limit
                if self.step_count > MAX_STEP_COUNT:
                    save_cache()
                    yield json.dumps({
                        "status": "error",
                        "message": "Search depth limit exceeded."
                    })
                    return
            
            save_cache()
            yield json.dumps({"status": "not_found", "message": "No path found."})

    async def _process_node(
        self, 
        current_node: str, 
        direction: str
    ) -> Optional[Dict]:
        """Process a single node: fetch links and filter to humans only."""
        async with self.semaphore:
            try:
                # Fetch candidates
                if direction == "forward":
                    _, candidates = await self._get_page_data(current_node)
                else:
                    candidates = await self._get_backlinks(current_node)

                # Heuristic filter
                filtered = self._heuristic_filter(candidates)
                
                # Shuffle to avoid bias
                random.shuffle(filtered)
                
                # Category-based person check
                candidates_to_check = filtered[:MAX_CANDIDATES_TO_CHECK]
                humans = await self._batch_check_categories(candidates_to_check)
                
                logger.info(
                    f"{current_node} ({direction}): "
                    f"{len(candidates)} → {len(filtered)} → {len(humans)} humans"
                )

                return {
                    "node": current_node,
                    "children": humans[:MAX_DEGREE],
                }
                
            except Exception as e:
                logger.error(f"Error processing {current_node}: {e}")
                return None

    async def _batch_check_categories(self, titles: List[str]) -> List[str]:
        """
        Check if Wikipedia articles are about humans using category analysis.
        Uses VIP fast lane + caching + API for maximum speed.
        """
        global _category_cache
        
        if not titles:
            return []
        
        # OPTIMIZATION 1: VIP Fast Lane (0ms)
        vip_humans = [t for t in titles if t in VIP_ALLOWLIST]
        remaining = [t for t in titles if t not in VIP_ALLOWLIST]
        
        # OPTIMIZATION 2: Cache Check
        cached_humans = []
        uncached = []
        
        for title in remaining:
            if title in _category_cache:
                if _category_cache[title]:
                    cached_humans.append(title)
            else:
                uncached.append(title)
        
        if not uncached:
            return vip_humans + cached_humans
        
        # OPTIMIZATION 3: Batch API Check
        batches = [
            uncached[i:i + CATEGORY_BATCH_SIZE] 
            for i in range(0, len(uncached), CATEGORY_BATCH_SIZE)
        ]
        
        async def check_batch(batch: List[str]) -> List[str]:
            humans = []
            params = {
                "action": "query",
                "format": "json",
                "titles": "|".join(batch),
                "prop": "categories",
                "cllimit": "max",
                "redirects": 1
            }
            headers = {"User-Agent": USER_AGENT}
            
            try:
                async with self.semaphore:
                    resp = await self.client.get(
                        WIKIPEDIA_API_URL, params=params, headers=headers
                    )
                
                if resp.status_code != 200:
                    return []
                
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                
                for page in pages.values():
                    title = page.get("title")
                    if "missing" in page:
                        _category_cache[title] = False
                        continue
                    
                    categories = [c["title"].lower() for c in page.get("categories", [])]
                    clean_cats = [c[9:] if c.startswith("category:") else c for c in categories]
                    
                    is_human = self._is_human(categories, clean_cats)
                    _category_cache[title] = is_human
                    
                    if is_human:
                        humans.append(title)
                        
            except Exception as e:
                logger.error(f"Batch check error: {e}")
            
            return humans

        tasks = [check_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        human_titles = []
        for result in results:
            if isinstance(result, Exception):
                continue
            human_titles.extend(result)
        
        return vip_humans + cached_humans + human_titles

    def _is_human(self, categories: List[str], clean_categories: List[str]) -> bool:
        """Determine if an article is about a human based on categories."""
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
                if any(role in cat for role in ["rulers", "people", "monarchs", "leaders", "generals"]):
                    return True
        
        return False

    async def _get_page_data(self, title: str) -> Tuple[str, List[str]]:
        """
        Fetch page extract and links with SMART PAGINATION.
        
        Uses early exit: stops fetching when >= 30 potential humans found.
        Limits to max 3 batches (1500 links) to prevent infinite loading.
        """
        global _page_cache
        
        if title in _page_cache:
            return _page_cache[title]
        
        headers = {"User-Agent": USER_AGENT}
        
        try:
            # Fetch extract
            params_text = {
                "action": "query", "format": "json", "titles": title,
                "prop": "extracts", "explaintext": 1, "exintro": 1
            }
            resp_text = await self.client.get(WIKIPEDIA_API_URL, params=params_text, headers=headers)
            
            text = ""
            for page in resp_text.json().get("query", {}).get("pages", {}).values():
                text = page.get("extract", "")
            
            # SMART PAGINATION for links
            params_links = {
                "action": "query", "format": "json", "titles": title,
                "prop": "links", "plnamespace": 0, "pllimit": "max"
            }
            
            all_links = []
            potential_humans = 0
            batch_count = 0
            
            while batch_count < MAX_FETCH_BATCHES:
                batch_count += 1
                
                resp_links = await self.client.get(
                    WIKIPEDIA_API_URL, params=params_links, headers=headers
                )
                data = resp_links.json()
                
                # Extract links from this batch
                new_links = []
                for page in data.get("query", {}).get("pages", {}).values():
                    if "links" in page:
                        new_links = [link["title"] for link in page["links"]]
                
                all_links.extend(new_links)
                
                # Check how many potential humans we have (quick heuristic filter)
                filtered = self._heuristic_filter(new_links)
                potential_humans += len(filtered)
                
                # EARLY EXIT: Stop if we have enough potential humans
                if potential_humans >= MIN_HUMANS_FOR_EARLY_EXIT:
                    break
                
                # Check if more pages available
                if "continue" not in data:
                    break
                
                params_links.update(data["continue"])
            
            result = (text, all_links)
            _page_cache[title] = result
            return result
            
        except Exception as e:
            logger.error(f"Error fetching {title}: {e}")
            return "", []

    async def _get_backlinks(self, title: str) -> List[str]:
        """
        Fetch backlinks with caching.
        Uses max limit (500) but NO pagination for speed.
        """
        global _backlink_cache
        
        if title in _backlink_cache:
            return _backlink_cache[title]
        
        headers = {"User-Agent": USER_AGENT}
        
        try:
            params = {
                "action": "query", "format": "json",
                "list": "backlinks", "bltitle": title,
                "blnamespace": 0, "bllimit": "max"  # max = 500, single batch
            }
            
            resp = await self.client.get(WIKIPEDIA_API_URL, params=params, headers=headers)
            data = resp.json()
            
            backlinks = []
            if "backlinks" in data.get("query", {}):
                backlinks = [bl["title"] for bl in data["query"]["backlinks"]]
            
            _backlink_cache[title] = backlinks
            return backlinks
            
        except Exception as e:
            logger.error(f"Error fetching backlinks for {title}: {e}")
            return []

    def _heuristic_filter(self, candidates: List[str]) -> List[str]:
        """
        Quick filter to remove obvious non-person articles.
        """
        filtered = []
        
        for candidate in candidates:
            if not candidate:
                continue
                
            lower = candidate.lower()
            
            # Skip years/dates
            if candidate[0].isdigit():
                continue
            
            # Skip "List of..." articles
            if candidate.startswith("List of"):
                continue
            
            # Skip meta-pages and tech articles
            if any(pattern in lower for pattern in META_PAGE_PATTERNS):
                continue
            
            filtered.append(candidate)
        
        return filtered


# =============================================================================
# PUBLIC API
# =============================================================================

async def find_shortest_path(start_page: str, end_page: str) -> AsyncGenerator[str, None]:
    """
    Main entry point for pathfinding.
    Streams JSON status messages for real-time progress updates.
    """
    searcher = BidirectionalBFS()
    async for msg in searcher.search(start_page, end_page):
        yield msg
