"""
Six Degrees of Wikipedia - Bidirectional BFS Engine (AGGRESSIVE MODE)

Key Features:
1. EXTENDED TIMEOUT: 100s to allow deep historical searches
2. LARGE BATCH SIZE: 50 titles per API call for better hub detection
3. GRACEFUL DEGRADATION: Falls back to heuristics if API times out
4. VIP Fast Lane: Instant verification for famous hub nodes
5. Smart Pagination: Early exit when enough humans found

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
# LOGGING
# =============================================================================

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# =============================================================================
# CONSTANTS (AGGRESSIVE MODE)
# =============================================================================

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "SixDegreesOfWikipedia/2.0 (capkimkhanh2k5@gmail.com)"

# Timeouts (AGGRESSIVE - extended for hard cases)
HARD_TIMEOUT_SECONDS = 100  # Extended from 50s
SOFT_TIMEOUT_SECONDS = 98   # Graceful exit before hard timeout

# Search limits
MAX_NODES_VISITED = 5000    # Increased for deeper searches
BATCH_SIZE = 25             # Nodes to process per iteration
CATEGORY_BATCH_SIZE = 30    # TUNED: 30 titles per API call (was 50, too aggressive)
MAX_CANDIDATES_TO_CHECK = 200

# Heartbeat settings
HEARTBEAT_INTERVAL_SECONDS = 3.0  # Send keepalive every 3 seconds
MAX_DEGREE = 30
MAX_STEP_COUNT = 300
CONCURRENT_REQUESTS = 15

# Smart Pagination
MIN_HUMANS_FOR_EARLY_EXIT = 25
MAX_FETCH_BATCHES = 3

# Fallback settings
FALLBACK_NODE_CAP = 20      # Slightly higher fallback cap
API_TIMEOUT = 15.0
BATCH_CHECK_TIMEOUT = 25.0  # Longer timeout for larger batches

# Cache files
CACHE_FILE = "wiki_cache.json"
CATEGORY_CACHE_FILE = "category_cache.json"
BACKLINK_CACHE_FILE = "backlink_cache.json"

# =============================================================================
# PERSON DETECTION
# =============================================================================

PERSON_POSITIVE_KEYWORDS = [
    "living people", "people from", "alumni", "players", "actors", "actresses",
    "politicians", "singers", "musicians", "writers", "directors", "scientists",
    "businesspeople", "entrepreneurs", "athletes", "journalists", "activists",
    "emperors", "monarchs", "khans", "sultans", "pharaohs", "tsars", "czars",
    "kings", "queens", "princes", "princesses", "dukes", "counts", "barons",
    "generals", "commanders", "admirals", "marshals", "warlords",
    "conquerors", "rulers", "regents", "caliphs", "popes", "patriarchs",
    "philosophers", "theologians", "historians", "mathematicians", "inventors",
    "explorers", "travelers", "missionaries",  # Added for Marco Polo
]

PERSON_NEGATIVE_KEYWORDS = [
    "animal", "horse", "racehorse", "dog", "cat breed", "species",
    "fictional", "character", "mythology", "mythological",
    "band", "musical group", "company", "organization", "corporation",
    "companies", "inc.", "llc", "ltd",
    "film", "movie", "song", "album", "book", "novel", "game",
    "place", "city", "country", "river", "mountain", "building",
    "event", "battle", "war", "treaty", "conference",
    "dynasty", "empire", "kingdom",
    "(pda)", "(software)", "(hardware)", "(operating system)",
    "computer", "device", "vehicle", "ship", "aircraft",
    "product", "series", "video game", "programming language",
    "technology", "software", "hardware", "smartphone", "tablet",
    "operating system", "application", "website",
]

PERSON_EXCEPTION_KEYWORDS = ["activist", "trainer", "owner", "engineer", "developer", "founder", "ceo"]

META_PAGE_PATTERNS = [
    "list of", "category:", "template:", "portal:", "help:", "wikipedia:", "file:",
    "user:", "talk:", "special:", "mediawiki:", "draft:", "timedtext:", "module:",
    "disambiguation", "timeline of", "history of", "geography of", "culture of",
    "economy of", "politics of", "government of", "military of",
    "(software)", "(operating system)", "(programming", "(computer", "(app)",
    "(company)", "(device)", "(product)", "(video game)", "(band)", "(film)",
]

# =============================================================================
# VIP FAST LANE - Expanded with Historical Connectors
# =============================================================================

VIP_ALLOWLIST = {
    # Modern World Leaders
    "Donald Trump", "Joe Biden", "Barack Obama", "George W. Bush", "Bill Clinton",
    "Hillary Clinton", "Vladimir Putin", "Xi Jinping", "Angela Merkel", "Emmanuel Macron",
    "Boris Johnson", "Narendra Modi", "Justin Trudeau", "Benjamin Netanyahu",
    
    # Historical Leaders - EXPANDED for Genghis Khan path
    "Genghis Khan", "Kublai Khan", "Marco Polo", "Alexander the Great", "Julius Caesar",
    "Augustus", "Napoleon Bonaparte", "Adolf Hitler", "Joseph Stalin",
    "Winston Churchill", "Franklin D. Roosevelt", "Theodore Roosevelt",
    "Queen Victoria", "Queen Elizabeth II", "King Charles III", "Henry VIII of England",
    "Cleopatra", "Ramesses II", "Charlemagne", "Peter the Great", "Catherine the Great",
    "Attila", "Tamerlane", "Saladin", "Richard I of England", "Frederick the Great",
    
    # Mongol Empire connectors
    "Ögedei Khan", "Güyük Khan", "Möngke Khan", "Jochi", "Chagatai Khan",
    "Tolui", "Batu Khan", "Hulagu Khan", "Berke", "Ariq Böke",
    
    # US Historical
    "Abraham Lincoln", "George Washington", "Thomas Jefferson", "John F. Kennedy",
    "Richard Nixon", "Ronald Reagan", "Jimmy Carter", "Dwight D. Eisenhower",
    "Harry S. Truman", "Lyndon B. Johnson", "Andrew Jackson", "Ulysses S. Grant",
    
    # Revolutionary Figures
    "Mahatma Gandhi", "Nelson Mandela", "Martin Luther King Jr.", "Che Guevara",
    "Ho Chi Minh", "Mao Zedong", "Vladimir Lenin", "Karl Marx", "Sun Yat-sen",
    "Fidel Castro", "Leon Trotsky", "Rosa Parks",
    
    # Tech Moguls
    "Elon Musk", "Jeff Bezos", "Bill Gates", "Steve Jobs", "Mark Zuckerberg",
    "Warren Buffett", "Larry Page", "Sergey Brin", "Tim Cook", "Satya Nadella",
    "Steve Wozniak", "Larry Ellison", "Jack Dorsey", "Peter Thiel", "Marc Andreessen",
    
    # Scientists & Explorers
    "Albert Einstein", "Isaac Newton", "Stephen Hawking", "Nikola Tesla",
    "Thomas Edison", "Marie Curie", "Charles Darwin", "Galileo Galilei",
    "Leonardo da Vinci", "Aristotle", "Plato", "Socrates", "Alan Turing",
    "Sigmund Freud", "Carl Jung", "Confucius",
    "Christopher Columbus", "Vasco da Gama", "Ferdinand Magellan", "Ibn Battuta",
    
    # Entertainment
    "Michael Jackson", "Elvis Presley", "Madonna", "Taylor Swift", "Beyoncé",
    "Leonardo DiCaprio", "Tom Hanks", "Brad Pitt", "Angelina Jolie",
    "Kanye West", "Oprah Winfrey", "Tom Cruise", "Will Smith",
    "Marilyn Monroe", "Audrey Hepburn", "Walt Disney",
    
    # Sports
    "Michael Jordan", "LeBron James", "Cristiano Ronaldo", "Lionel Messi",
    "Muhammad Ali", "Tiger Woods", "Serena Williams", "Roger Federer",
    "Babe Ruth", "Pelé", "Mike Tyson",
    
    # Religious/Spiritual
    "Pope Francis", "Dalai Lama", "Mother Teresa", "Pope John Paul II",
}

# =============================================================================
# CACHE
# =============================================================================

_page_cache: Dict[str, Tuple[str, List[str]]] = {}
_category_cache: Dict[str, bool] = {}
_backlink_cache: Dict[str, List[str]] = {}


def load_cache() -> None:
    global _page_cache, _category_cache, _backlink_cache
    for cache_file, name in [(CACHE_FILE, "page"), (CATEGORY_CACHE_FILE, "category"), (BACKLINK_CACHE_FILE, "backlink")]:
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
            except Exception:
                pass


def save_cache() -> None:
    for cache_file, data in [(CACHE_FILE, _page_cache), (CATEGORY_CACHE_FILE, _category_cache), (BACKLINK_CACHE_FILE, _backlink_cache)]:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass


load_cache()


# =============================================================================
# BFS ENGINE
# =============================================================================

class BidirectionalBFS:
    """Bidirectional BFS with AGGRESSIVE settings for hard cases."""

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

    def _reconstruct_path(self, node: str, parent_map: Dict[str, Optional[str]], reverse: bool = False) -> List[str]:
        path = []
        current = node
        while current is not None:
            path.append(current)
            current = parent_map.get(current)
        return path if reverse else path[::-1]

    async def search(self, start_node: str, end_node: str) -> AsyncGenerator[str, None]:
        """Main search with HARD TIMEOUT guarantee."""
        self.start_page = start_node
        self.end_page = end_node

        async def collect():
            results = []
            async for msg in self._search_impl():
                results.append(msg)
            return results

        try:
            messages = await asyncio.wait_for(collect(), timeout=HARD_TIMEOUT_SECONDS)
            for msg in messages:
                yield msg
        except asyncio.TimeoutError:
            save_cache()
            yield json.dumps({"status": "error", "message": f"HARD TIMEOUT after {HARD_TIMEOUT_SECONDS}s"})
        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)})

    async def _search_impl(self) -> AsyncGenerator[str, None]:
        self.start_time = time.time()
        self.last_heartbeat = time.time()  # Track last heartbeat
        self.queue_f = deque([self.start_page])
        self.parent_f = {self.start_page: None}
        self.queue_b = deque([self.end_page])
        self.parent_b = {self.end_page: None}
        self.step_count = 0

        limits = httpx.Limits(max_keepalive_connections=CONCURRENT_REQUESTS, max_connections=30)

        async with httpx.AsyncClient(limits=limits, timeout=API_TIMEOUT) as client:
            self.client = client

            yield json.dumps({"status": "info", "message": f"Searching: {self.start_page} <-> {self.end_page}"})

            while self.queue_f and self.queue_b:
                elapsed = time.time() - self.start_time
                total_visited = len(self.parent_f) + len(self.parent_b)

                # SOFT TIMEOUT: Graceful exit before watchdog
                if elapsed > SOFT_TIMEOUT_SECONDS:
                    save_cache()
                    yield json.dumps({
                        "status": "error",
                        "message": f"Search time limit reached ({SOFT_TIMEOUT_SECONDS}s). Graceful exit."
                    })
                    return

                if total_visited > MAX_NODES_VISITED:
                    save_cache()
                    yield json.dumps({"status": "error", "message": f"Node limit ({MAX_NODES_VISITED})"})
                    return

                self.step_count += 1

                if len(self.queue_f) <= len(self.queue_b):
                    direction, queue = "forward", self.queue_f
                    parent_own, parent_other = self.parent_f, self.parent_b
                else:
                    direction, queue = "backward", self.queue_b
                    parent_own, parent_other = self.parent_b, self.parent_f

                level_nodes = [queue.popleft() for _ in range(min(len(queue), BATCH_SIZE))]

                yield json.dumps({
                    "status": "exploring", "direction": direction, "nodes": level_nodes,
                    "stats": {"visited": total_visited, "time": round(elapsed, 1)}
                })
                
                # Update heartbeat timestamp after exploration message
                self.last_heartbeat = time.time()

                tasks = [self._process_node(node, direction) for node in level_nodes]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
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
                    yield json.dumps({"status": "error", "message": "Step limit"})
                    return
                
                # Send heartbeat if no message sent in HEARTBEAT_INTERVAL_SECONDS
                now = time.time()
                if now - self.last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                    yield json.dumps({
                        "status": "heartbeat",
                        "time": round(elapsed, 1),
                        "visited": total_visited,
                        "message": "Search in progress..."
                    })
                    self.last_heartbeat = now

            save_cache()
            yield json.dumps({"status": "not_found", "message": "No path found"})

    async def _process_node(self, current_node: str, direction: str) -> Optional[Dict]:
        """Process node with GRACEFUL DEGRADATION."""
        try:
            async with self.semaphore:
                if direction == "forward":
                    _, candidates = await self._get_page_data(current_node)
                else:
                    candidates = await self._get_backlinks(current_node)

                filtered = self._heuristic_filter(candidates)
                random.shuffle(filtered)

                to_check = filtered[:MAX_CANDIDATES_TO_CHECK]
                humans = await self._batch_check_categories_safe(to_check)

                logger.info(f"{current_node} ({direction}): {len(candidates)} → {len(filtered)} → {len(humans)} humans")

                return {"node": current_node, "children": humans[:MAX_DEGREE]}

        except Exception as e:
            logger.error(f"Error processing {current_node}: {e}")
            return None

    async def _batch_check_categories_safe(self, titles: List[str]) -> List[str]:
        """GRACEFUL DEGRADATION: Return capped fallback on timeout."""
        if not titles:
            return []

        try:
            return await asyncio.wait_for(
                self._batch_check_categories(titles),
                timeout=BATCH_CHECK_TIMEOUT
            )
        except asyncio.TimeoutError:
            vips = [t for t in titles if t in VIP_ALLOWLIST]
            others = [t for t in titles if t not in VIP_ALLOWLIST]
            fallback = vips + others[:FALLBACK_NODE_CAP]
            dropped = len(titles) - len(fallback)
            logger.warning(f"Batch check timed out. Returning {len(fallback)} nodes (dropped {dropped}).")
            return fallback
        except Exception as e:
            logger.error(f"Batch check failed: {e}. Using fallback.")
            vips = [t for t in titles if t in VIP_ALLOWLIST]
            others = [t for t in titles if t not in VIP_ALLOWLIST]
            return vips + others[:FALLBACK_NODE_CAP]

    async def _batch_check_categories(self, titles: List[str]) -> List[str]:
        """Check if articles are about humans via API."""
        global _category_cache

        # VIP Fast Lane
        vips = [t for t in titles if t in VIP_ALLOWLIST]
        remaining = [t for t in titles if t not in VIP_ALLOWLIST]

        # Cache check
        cached = [t for t in remaining if _category_cache.get(t, False)]
        uncached = [t for t in remaining if t not in _category_cache]

        if not uncached:
            return vips + cached

        # API batch check with LARGER batches (50 titles each)
        batches = [uncached[i:i + CATEGORY_BATCH_SIZE] for i in range(0, len(uncached), CATEGORY_BATCH_SIZE)]

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
            except Exception:
                return []

        results = await asyncio.gather(*[check_batch(b) for b in batches], return_exceptions=True)
        api_humans = []
        for r in results:
            if isinstance(r, Exception):
                continue
            api_humans.extend(r)

        return vips + cached + api_humans

    def _is_human(self, categories: List[str], clean_categories: List[str]) -> bool:
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
                if any(r in cat for r in ["rulers", "people", "monarchs", "leaders", "explorers"]):
                    return True
        return False

    async def _get_page_data(self, title: str) -> Tuple[str, List[str]]:
        """Fetch with smart pagination."""
        global _page_cache

        if title in _page_cache:
            return _page_cache[title]

        headers = {"User-Agent": USER_AGENT}

        try:
            resp = await self.client.get(
                WIKIPEDIA_API_URL,
                params={"action": "query", "format": "json", "titles": title,
                        "prop": "extracts", "explaintext": 1, "exintro": 1},
                headers=headers
            )
            text = ""
            for p in resp.json().get("query", {}).get("pages", {}).values():
                text = p.get("extract", "")

            params = {"action": "query", "format": "json", "titles": title,
                      "prop": "links", "plnamespace": 0, "pllimit": "max"}

            all_links = []
            potential_humans = 0

            for _ in range(MAX_FETCH_BATCHES):
                resp = await self.client.get(WIKIPEDIA_API_URL, params=params, headers=headers)
                data = resp.json()

                new_links = []
                for p in data.get("query", {}).get("pages", {}).values():
                    if "links" in p:
                        new_links = [l["title"] for l in p["links"]]

                all_links.extend(new_links)
                potential_humans += len(self._heuristic_filter(new_links))

                if potential_humans >= MIN_HUMANS_FOR_EARLY_EXIT:
                    break
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
        """Fetch backlinks (single batch)."""
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
        """Quick filter for non-person articles."""
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
    """Main entry point."""
    searcher = BidirectionalBFS()
    async for msg in searcher.search(start_page, end_page):
        yield msg
