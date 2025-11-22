import asyncio
import json
import httpx
from collections import deque
from typing import List, Set, Dict, Optional, AsyncGenerator
from .llm_client import verify_candidates_with_llm

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

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

        while self.queue_start and self.queue_end:
            self.step_count += 1
            
            # Optimization: Expand the smaller queue
            if len(self.queue_start) <= len(self.queue_end):
                direction = "forward"
                current_queue = self.queue_start
                current_visited = self.visited_start
                other_visited = self.visited_end
                target_node = self.end_page
            else:
                direction = "backward"
                current_queue = self.queue_end
                current_visited = self.visited_end
                other_visited = self.visited_start
                target_node = self.start_page

            current_node = current_queue.popleft()
            yield json.dumps({"status": "visiting", "node": current_node, "direction": direction, "step": self.step_count})

            # 1. Fetch Data (Text + Links)
            # For backward search, we need backlinks, not forward links.
            if direction == "forward":
                wiki_text, candidates = await self.get_page_data(current_node)
            else:
                wiki_text, candidates = await self.get_backlinks_data(current_node)
            
            print(f"DEBUG: {current_node} - Raw Candidates: {len(candidates)}")
            if not candidates:
                continue

            # 2. Heuristic Filter (Fast)
            filtered_candidates = self.heuristic_filter(candidates)
            print(f"DEBUG: {current_node} - Heuristic Filtered: {len(filtered_candidates)}")
            
            # 3. LLM Verification (Smart Layer)
            # Only verify if we have a reasonable number of candidates
            valid_neighbors = []
            
            if direction == "forward":
                # Verify with LLM
                # Batching if necessary (handled in llm_client or here)
                verified_objs = await verify_candidates_with_llm(wiki_text, current_node, target_node, filtered_candidates)
                print(f"DEBUG: {current_node} - LLM Verified: {len(verified_objs)}")
                
                # Sort by priority (is_bridge)
                verified_objs.sort(key=lambda x: x.get("is_bridge", False), reverse=True)
                valid_neighbors = [x["name"] for x in verified_objs]
            else:
                # Backward: Just use heuristic filtered links (Backlinks)
                # LLM verification on backlinks is harder because we lack context of the *source* page easily.
                # We trust structural backlinks more, or we can add a simple check if needed.
                valid_neighbors = filtered_candidates

            # 4. Path Construction
            for neighbor in valid_neighbors:
                if neighbor in other_visited:
                    # Intersection Found!
                    current_visited[neighbor] = current_node
                    path = self.reconstruct_path(neighbor, direction)
                    yield json.dumps({"status": "finished", "path": path})
                    return

                if neighbor not in current_visited:
                    current_visited[neighbor] = current_node
                    current_queue.append(neighbor)

        yield json.dumps({"status": "error", "message": "No path found."})

    async def get_page_data(self, title: str):
        # Fetch Intro + Links
        params = {
            "action": "query", "format": "json", "titles": title,
            "prop": "extracts", "explaintext": 1, "exintro": 1,
            "generator": "links", "gplnamespace": 0, "gpllimit": "max"
        }
        try:
            # Split into two requests for reliability
            # 1. Text
            text_resp = await self.client.get(API_URL, params={
                "action": "query", "format": "json", "titles": title, 
                "prop": "extracts", "explaintext": 1, "exintro": 1
            })
            text_data = text_resp.json()
            pages = text_data.get("query", {}).get("pages", {})
            text = ""
            for _, p in pages.items(): text = p.get("extract", "")
            
            # 2. Links
            link_resp = await self.client.get(API_URL, params={
                "action": "query", "format": "json", "titles": title,
                "generator": "links", "gplnamespace": 0, "gpllimit": "max"
            })
            link_data = link_resp.json()
            link_pages = link_data.get("query", {}).get("pages", {})
            links = [p["title"] for _, p in link_pages.items() if "title" in p]
            
            return text, links
        except:
            return "", []

    async def get_backlinks_data(self, title: str):
        # Fetch Backlinks
        # We don't really have "text" for the backlink source easily unless we fetch each one.
        # So we return empty text.
        params = {
            "action": "query", "format": "json", "list": "backlinks",
            "bltitle": title, "bllimit": "max", "blnamespace": 0
        }
        try:
            resp = await self.client.get(API_URL, params=params)
            data = resp.json()
            links = [item["title"] for item in data.get("query", {}).get("backlinks", [])]
            return "", links
        except:
            return "", []

    def heuristic_filter(self, candidates: List[str]) -> List[str]:
        # Filter out dates, years, generic terms
        filtered = []
        for c in candidates:
            if c[0].isdigit(): continue # Years/Dates
            if "List of" in c: continue
            if "Category:" in c: continue
            if "Template:" in c: continue
            if "Wikipedia:" in c: continue
            if "Help:" in c: continue
            if "Portal:" in c: continue
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
    async with httpx.AsyncClient(limits=limits, timeout=60.0) as client:
        searcher = BFS_Search(start_page, end_page, client)
        async for msg in searcher.search():
            yield msg
