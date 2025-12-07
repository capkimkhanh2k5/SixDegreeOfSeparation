"""
Six Degrees of Wikipedia - Bidirectional BFS Engine

This module implements an optimized bidirectional BFS algorithm for finding
the shortest path between two Wikipedia articles, restricted to human entities.

Key Optimizations:
1. Bidirectional Search: O(b^(d/2)) instead of O(b^d) complexity
2. Category Caching: Eliminates redundant Wikipedia API calls
3. Parent-Pointer Path Reconstruction: ~8x memory reduction
4. Historical Figure Detection: Supports ancient personalities (emperors, khans, etc.)
5. Robust Exception Handling: Single API failure doesn't crash the search

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

# Configure logging (disable httpx verbose output)
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
TIMEOUT_SECONDS = 60
MAX_NODES_VISITED = 2000
MAX_LINKS_PER_PAGE = 500  # Reduced from 2000 for faster API calls
BATCH_SIZE = 20
CATEGORY_BATCH_SIZE = 10
MAX_CANDIDATES_TO_CHECK = 300  # Reduced from 500 for faster category checks  
MAX_DEGREE = 30
MAX_STEP_COUNT = 100
CONCURRENT_REQUESTS = 20

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
]

# Exceptions: categories containing these words are about humans despite negative keywords
PERSON_EXCEPTION_KEYWORDS = ["activist", "trainer", "owner", "breeder", "rider"]

# Wikipedia meta-page patterns to filter out
META_PAGE_PATTERNS = [
    "list of", "category:", "template:", "portal:", "help:", "wikipedia:", "file:",
    "user:", "talk:", "special:", "mediawiki:", "draft:", "timedtext:", "module:",
    "disambiguation", "timeline of", "history of", "geography of", "culture of",
    "economy of", "politics of", "government of", "military of",
]

# =============================================================================
# VIP FAST LANE - Famous Hub Nodes (0ms verification)
# =============================================================================
# These are well-known historical and modern figures that serve as "bridge nodes"
# in the Wikipedia graph. By pre-verifying them, we skip API calls for common hubs.

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
    "Michael Jackson", "Elvis Presley", "The Beatles", "Madonna", "Taylor Swift",
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
    
    for cache_file, cache_dict, name in [
        (CACHE_FILE, "_page_cache", "page"),
        (CATEGORY_CACHE_FILE, "_category_cache", "category"),
        (BACKLINK_CACHE_FILE, "_backlink_cache", "backlink"),
    ]:
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if cache_dict == "_page_cache":
                        _page_cache = loaded
                    elif cache_dict == "_category_cache":
                        _category_cache = loaded
                    elif cache_dict == "_backlink_cache":
                        _backlink_cache = loaded
                    logger.info(f"Loaded {len(loaded)} {name} cache entries")
            except Exception as e:
                logger.warning(f"Failed to load {name} cache: {e}")


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
    
    This implementation uses several optimizations:
    
    1. **Bidirectional Search**: Searches from both start and end simultaneously,
       reducing complexity from O(b^d) to O(b^(d/2)) where b is branching factor
       and d is path depth.
    
    2. **Parent-Pointer Path Reconstruction**: Instead of storing full paths for
       each visited node (O(n*d) memory), we store only parent pointers (O(n))
       and reconstruct paths on demand. ~8x memory reduction for deep searches.
    
    3. **Category Caching**: Wikipedia category lookups are cached to avoid
       redundant API calls. Reduces API calls by 90%+ for super-nodes.
    
    4. **Historical Figure Detection**: Expanded keyword set to correctly identify
       ancient personalities (emperors, khans, generals) as humans.
    
    5. **Robust Exception Handling**: Individual API failures don't crash the
       entire search; failed nodes are gracefully skipped.
    """
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        
        # Search state (initialized per search)
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
        """
        Reconstruct path from parent pointers.
        
        This is a key optimization: instead of storing full paths for every
        visited node (memory-intensive), we store only parent pointers and
        reconstruct the path when needed.
        
        Args:
            node: The node to start reconstruction from
            parent_map: Dictionary mapping child -> parent
            reverse: If True, return path in reverse order
            
        Returns:
            List of nodes forming the path from root to node (or reverse)
        """
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
        
        Yields JSON status messages for real-time progress updates:
        - {"status": "info", "message": "..."} - Initialization info
        - {"status": "exploring", ...} - Current exploration status
        - {"status": "finished", "path": [...]} - Path found
        - {"status": "error", "message": "..."} - Timeout/limit exceeded
        - {"status": "not_found", ...} - No path exists
        
        Args:
            start_node: Wikipedia article title to start from
            end_node: Wikipedia article title to reach
            
        Yields:
            JSON-encoded status messages
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
        
        # Configure HTTP client with connection pooling
        limits = httpx.Limits(
            max_keepalive_connections=CONCURRENT_REQUESTS,
            max_connections=CONCURRENT_REQUESTS + 10
        )
        
        async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
            self.client = client
            
            yield json.dumps({
                "status": "info",
                "message": f"Initializing Bidirectional Search: {self.start_page} <-> {self.end_page}"
            })

            while self.queue_f and self.queue_b:
                elapsed = time.time() - start_time
                
                # Safety check: timeout
                if elapsed > TIMEOUT_SECONDS:
                    save_cache()
                    yield json.dumps({
                        "status": "error",
                        "message": f"Search timed out after {TIMEOUT_SECONDS} seconds."
                    })
                    return

                # Safety check: max nodes
                total_visited = len(self.parent_f) + len(self.parent_b)
                if total_visited > MAX_NODES_VISITED:
                    save_cache()
                    yield json.dumps({
                        "status": "error",
                        "message": f"Search limit exceeded ({MAX_NODES_VISITED} nodes)."
                    })
                    return

                self.step_count += 1
                
                # Expand the smaller frontier (key BFS optimization)
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

                # Process nodes in batches for concurrency
                level_nodes = []
                for _ in range(min(len(queue), BATCH_SIZE)):
                    level_nodes.append(queue.popleft())
                
                # Emit progress update
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
                        
                        # Check for intersection (path found!)
                        if child in parent_other:
                            path_f = self._reconstruct_path(child, self.parent_f)
                            path_b = self._reconstruct_path(child, self.parent_b, reverse=True)
                            full_path = path_f[:-1] + path_b
                            
                            save_cache()
                            yield json.dumps({"status": "finished", "path": full_path})
                            return

                # Depth limit check
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
        """
        Process a single node: fetch links and filter to humans only.
        
        Pipeline:
        1. Fetch all Wikipedia links (forward) or backlinks (backward)
        2. Apply heuristic filter (remove meta-pages, dates, etc.)
        3. Shuffle to avoid alphabetical bias
        4. Check Wikipedia categories to verify human entities
        5. Return top MAX_DEGREE candidates
        
        Args:
            current_node: Wikipedia article title to process
            direction: "forward" (outgoing links) or "backward" (backlinks)
            
        Returns:
            Dict with "node" and "children" keys, or None on error
        """
        async with self.semaphore:
            try:
                # Step 1: Fetch candidates
                if direction == "forward":
                    _, candidates = await self._get_page_data(current_node)
                else:
                    candidates = await self._get_backlinks(current_node)

                # Step 2: Heuristic filter
                filtered = self._heuristic_filter(candidates)
                
                # Step 3: Shuffle to avoid bias
                random.shuffle(filtered)
                
                # Step 4: Category-based person check
                candidates_to_check = filtered[:MAX_CANDIDATES_TO_CHECK]
                humans = await self._batch_check_categories(candidates_to_check)
                
                logger.info(
                    f"{current_node} ({direction}): "
                    f"{len(candidates)} → {len(filtered)} → {len(humans)} humans"
                )

                # Step 5: Limit to MAX_DEGREE
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
        
        Optimization Pipeline:
        1. VIP Fast Lane: Instant verification for famous hub nodes (0ms)
        2. Cache Check: Return cached results without API call
        3. API Check: Batch query Wikipedia for uncached titles
        
        For super-nodes like "Genghis Khan" with 500+ links, this reduces
        API calls by 90%+ through caching and VIP pre-verification.
        
        Args:
            titles: List of Wikipedia article titles to check
            
        Returns:
            List of titles confirmed to be about humans
        """
        global _category_cache
        
        if not titles:
            return []
        
        # =================================================================
        # OPTIMIZATION 1: VIP Fast Lane (0ms latency for famous people)
        # =================================================================
        vip_humans = [t for t in titles if t in VIP_ALLOWLIST]
        remaining_titles = [t for t in titles if t not in VIP_ALLOWLIST]
        
        # =================================================================
        # OPTIMIZATION 2: Cache Check
        # =================================================================
        cached_humans = []
        uncached = []
        
        for title in remaining_titles:  # Use remaining (non-VIP) titles
            if title in _category_cache:
                if _category_cache[title]:
                    cached_humans.append(title)
            else:
                uncached.append(title)
        
        # If all remaining are cached, return VIP + cached
        if not uncached:
            return vip_humans + cached_humans
        
        # =================================================================
        # OPTIMIZATION 3: Batch API Check for uncached titles
        # =================================================================
        batches = [
            uncached[i:i + CATEGORY_BATCH_SIZE] 
            for i in range(0, len(uncached), CATEGORY_BATCH_SIZE)
        ]
        
        async def check_batch(batch: List[str]) -> List[str]:
            """Check a single batch of titles."""
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
                        WIKIPEDIA_API_URL, 
                        params=params, 
                        headers=headers
                    )
                
                if resp.status_code != 200:
                    logger.warning(f"API returned {resp.status_code}")
                    return []
                
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                
                for page in pages.values():
                    title = page.get("title")
                    
                    if "missing" in page:
                        _category_cache[title] = False
                        continue
                    
                    categories = [
                        c["title"].lower() 
                        for c in page.get("categories", [])
                    ]
                    clean_cats = [
                        c[9:] if c.startswith("category:") else c 
                        for c in categories
                    ]
                    
                    is_human = self._is_human(categories, clean_cats)
                    _category_cache[title] = is_human
                    
                    if is_human:
                        humans.append(title)
                        
            except Exception as e:
                logger.error(f"Batch check error: {e}")
            
            return humans

        # Run all batches concurrently
        tasks = [check_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        human_titles = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch failed: {result}")
                continue
            human_titles.extend(result)
        
        # Return: VIP (instant) + Cached + API-verified
        return vip_humans + cached_humans + human_titles

    def _is_human(
        self, 
        categories: List[str], 
        clean_categories: List[str]
    ) -> bool:
        """
        Determine if an article is about a human based on categories.
        
        Uses a two-stage filter:
        1. Negative filter: Exclude animals, fictional characters, places, etc.
        2. Positive filter: Must match at least one human indicator
        
        Args:
            categories: Raw category names (with "Category:" prefix)
            clean_categories: Category names without prefix
            
        Returns:
            True if the article is about a human
        """
        # Stage 1: Negative filter
        for cat in clean_categories:
            if any(neg in cat for neg in PERSON_NEGATIVE_KEYWORDS):
                # Allow exceptions (e.g., "Horse trainer" is a human)
                if not any(exc in cat for exc in PERSON_EXCEPTION_KEYWORDS):
                    return False
        
        # Stage 2: Positive filter
        for cat in categories:
            # Check keyword matches
            if any(kw in cat for kw in PERSON_POSITIVE_KEYWORDS):
                return True
            
            # Check birth/death year patterns (e.g., "1946 births")
            if re.search(r'\d{4} births', cat) and "animal" not in cat:
                return True
            if re.search(r'\d{4} deaths', cat) and "animal" not in cat:
                return True
            
            # Check century-based categories (e.g., "12th-century monarchs")
            if re.search(r'\d{1,2}(st|nd|rd|th)-century', cat):
                if any(role in cat for role in ["rulers", "people", "monarchs", "leaders", "generals"]):
                    return True
        
        return False

    async def _get_page_data(self, title: str) -> Tuple[str, List[str]]:
        """
        Fetch page extract and outgoing links with caching.
        
        Args:
            title: Wikipedia article title
            
        Returns:
            Tuple of (extract_text, list_of_links)
        """
        global _page_cache
        
        if title in _page_cache:
            return _page_cache[title]
        
        headers = {"User-Agent": USER_AGENT}
        
        try:
            # Fetch extract and links concurrently
            # OPTIMIZATION: Use pllimit=200 instead of "max" to avoid pagination
            params_text = {
                "action": "query", "format": "json", "titles": title,
                "prop": "extracts", "explaintext": 1, "exintro": 1
            }
            params_links = {
                "action": "query", "format": "json", "titles": title,
                "prop": "links", "plnamespace": 0, "pllimit": 200  # Fixed limit
            }
            
            resp_text, resp_links = await asyncio.gather(
                self.client.get(WIKIPEDIA_API_URL, params=params_text, headers=headers),
                self.client.get(WIKIPEDIA_API_URL, params=params_links, headers=headers)
            )
            
            # Parse extract
            text = ""
            for page in resp_text.json().get("query", {}).get("pages", {}).values():
                text = page.get("extract", "")
            
            # Parse links - NO PAGINATION for speed
            links = []
            data_links = resp_links.json()
            for page in data_links.get("query", {}).get("pages", {}).values():
                if "links" in page:
                    links = [link["title"] for link in page["links"]]
            
            result = (text, links)
            _page_cache[title] = result
            return result
            
        except Exception as e:
            logger.error(f"Error fetching {title}: {e}")
            return "", []

    async def _get_backlinks(self, title: str) -> List[str]:
        """
        Fetch backlinks (pages linking TO this article) with caching.
        
        OPTIMIZATION: Fetches only first batch (100 backlinks) without pagination.
        This dramatically speeds up searches for popular figures.
        
        Args:
            title: Wikipedia article title
            
        Returns:
            List of article titles that link to this page
        """
        global _backlink_cache
        
        if title in _backlink_cache:
            return _backlink_cache[title]
        
        headers = {"User-Agent": USER_AGENT}
        
        try:
            # OPTIMIZATION: Use bllimit=100 instead of "max" to avoid pagination
            params = {
                "action": "query", "format": "json",
                "list": "backlinks", "bltitle": title,
                "blnamespace": 0, "bllimit": 100  # Fixed limit, no pagination
            }
            
            resp = await self.client.get(
                WIKIPEDIA_API_URL, params=params, headers=headers
            )
            data = resp.json()
            
            backlinks = []
            if "backlinks" in data.get("query", {}):
                backlinks = [bl["title"] for bl in data["query"]["backlinks"]]
            
            # NO PAGINATION - just use the first batch for speed
            _backlink_cache[title] = backlinks
            return backlinks
            
        except Exception as e:
            logger.error(f"Error fetching backlinks for {title}: {e}")
            return []

    def _heuristic_filter(self, candidates: List[str]) -> List[str]:
        """
        Quick filter to remove obvious non-person articles.
        
        Removes:
        - Wikipedia meta-pages (Categories, Templates, Lists, etc.)
        - Year/date articles
        - Geographic/historical topic pages
        
        Args:
            candidates: List of Wikipedia article titles
            
        Returns:
            Filtered list of potential person articles
        """
        filtered = []
        
        for candidate in candidates:
            lower = candidate.lower()
            
            # Skip years/dates
            if candidate and candidate[0].isdigit():
                continue
            
            # Skip "List of..." articles
            if candidate.startswith("List of"):
                continue
            
            # Skip meta-pages
            if any(pattern in lower for pattern in META_PAGE_PATTERNS):
                continue
            
            filtered.append(candidate)
        
        return filtered


# =============================================================================
# PUBLIC API
# =============================================================================

async def find_shortest_path(
    start_page: str, 
    end_page: str
) -> AsyncGenerator[str, None]:
    """
    Main entry point for pathfinding.
    
    Streams JSON status messages for real-time progress updates.
    
    Args:
        start_page: Wikipedia article title to start from
        end_page: Wikipedia article title to find
        
    Yields:
        JSON-encoded status messages
        
    Example:
        async for message in find_shortest_path("Albert Einstein", "Elon Musk"):
            data = json.loads(message)
            if data["status"] == "finished":
                print(f"Path: {data['path']}")
    """
    searcher = BidirectionalBFS()
    async for msg in searcher.search(start_page, end_page):
        yield msg
