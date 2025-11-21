import asyncio
import httpx
from collections import deque
from typing import List, Optional, Set, Dict

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

async def get_links(client: httpx.AsyncClient, title: str) -> Set[str]:
    """
    Fetches all forward links from a given Wikipedia page.
    Filters for Main namespace (ns=0) only.
    """
    links = set()
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "links",
        "plnamespace": 0,  # Main namespace only
        "pllimit": "max",  # Max 500 for standard users
    }

    try:
        while True:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1": # Page does not exist
                    continue
                if "links" in page_data:
                    for link in page_data["links"]:
                        links.add(link["title"])

            if "continue" in data:
                params.update(data["continue"])
            else:
                break
    except Exception as e:
        print(f"Error fetching links for {title}: {e}")
        
    return links

async def get_backlinks(client: httpx.AsyncClient, title: str) -> Set[str]:
    """
    Fetches all pages that link TO a given Wikipedia page (backlinks).
    Filters for Main namespace (ns=0) only.
    """
    backlinks = set()
    params = {
        "action": "query",
        "format": "json",
        "list": "backlinks",
        "bltitle": title,
        "blnamespace": 0, # Main namespace only
        "bllimit": "max",
    }

    try:
        while True:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "query" in data and "backlinks" in data["query"]:
                for link in data["query"]["backlinks"]:
                    backlinks.add(link["title"])

            if "continue" in data:
                params.update(data["continue"])
            else:
                break
    except Exception as e:
        print(f"Error fetching backlinks for {title}: {e}")

    return backlinks

def reconstruct_path(visited_start: Dict[str, Optional[str]], visited_end: Dict[str, Optional[str]], meeting_point: str) -> List[str]:
    """
    Reconstructs the path from start to end passing through the meeting point.
    """
    # Path from start to meeting_point
    path_start = []
    curr = meeting_point
    while curr is not None:
        path_start.append(curr)
        curr = visited_start[curr]
    path_start.reverse()

    # Path from meeting_point to end
    path_end = []
    curr = visited_end[meeting_point] # Start from the parent of meeting_point in the end search
    while curr is not None:
        path_end.append(curr)
        curr = visited_end[curr]
    
    return path_start + path_end

async def bidirectional_bfs(start_page: str, end_page: str) -> Optional[List[str]]:
    """
    Finds the shortest path between two Wikipedia pages using Bi-directional BFS.
    """
    if start_page == end_page:
        return [start_page]

    # Async client with limits to avoid overwhelming the API
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    headers = {
        "User-Agent": "WikiShortestPathBot/1.0 (http://example.com/bot; bot@example.com)"
    }
    async with httpx.AsyncClient(limits=limits, timeout=10.0, headers=headers) as client:
        # Check if pages exist (optional optimization, but good for early exit)
        # For now, we'll let the first fetch handle existence checks implicitly (empty links)
        
        # Queues for BFS
        queue_start = deque([start_page])
        queue_end = deque([end_page])

        # Visited sets keeping track of parents for path reconstruction
        # Key: Node, Value: Parent
        visited_start: Dict[str, Optional[str]] = {start_page: None}
        visited_end: Dict[str, Optional[str]] = {end_page: None}

        while queue_start and queue_end:
            # Expand the smaller queue to optimize search
            if len(queue_start) <= len(queue_end):
                current_node = queue_start.popleft()
                
                # Get forward links
                neighbors = await get_links(client, current_node)
                
                for neighbor in neighbors:
                    if neighbor in visited_end:
                        visited_start[neighbor] = current_node
                        return reconstruct_path(visited_start, visited_end, neighbor)
                    
                    if neighbor not in visited_start:
                        visited_start[neighbor] = current_node
                        queue_start.append(neighbor)
            else:
                current_node = queue_end.popleft()
                
                # Get backward links (pages that link to current_node)
                neighbors = await get_backlinks(client, current_node)
                
                for neighbor in neighbors:
                    if neighbor in visited_start:
                        visited_end[neighbor] = current_node
                        return reconstruct_path(visited_start, visited_end, neighbor)
                    
                    if neighbor not in visited_end:
                        visited_end[neighbor] = current_node
                        queue_end.append(neighbor)

    return None

async def main():
    start = "Python (programming language)"
    end = "Philosophy" 
    
    print(f"Finding path from '{start}' to '{end}'...")
    path = await bidirectional_bfs(start, end)
    
    if path:
        print(f"Path found ({len(path)} steps):")
        print(" -> ".join(path))
    else:
        print("No path found.")

if __name__ == "__main__":
    asyncio.run(main())
