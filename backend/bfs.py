import httpx
from collections import deque
from typing import List, Optional, Set, Dict
from bs4 import BeautifulSoup
import json
from typing import AsyncGenerator

# Wikipedia API Endpoint
API_URL = "https://en.wikipedia.org/w/api.php"

async def get_links(client: httpx.AsyncClient, title: str) -> Set[str]:
    """
    Fetches forward links from a Wikipedia page, filtering for:
    1. Links that appear in body paragraphs (not navboxes/infoboxes/lists)
    2. Pages that describe people
    
    Hybrid approach: Use generator=links for speed, but fetch HTML to identify
    which links are in body content vs templates.
    """
    links = set()
    
    # Step 1: Fetch HTML to identify body paragraph links
    body_links = set()
    parse_params = {
        "action": "parse",
        "format": "json",
        "page": title,
        "prop": "text",
        "disableeditsection": 1,
        "disabletoc": 1
    }
    
    try:
        parse_response = await client.get(API_URL, params=parse_params)
        parse_response.raise_for_status()
        parse_data = parse_response.json()
        
        if "error" not in parse_data:
            html_content = parse_data.get("parse", {}).get("text", {}).get("*", "")
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                parser_output = soup.find('div', class_='mw-parser-output')
                
                if parser_output:
                    # Remove unwanted sections
                    for element in parser_output.find_all(['table', 'div'], class_=['navbox', 'infobox', 'metadata', 'sistersitebox']):
                        element.decompose()
                    
                    # Remove "See also", "References", etc.
                    for heading in parser_output.find_all(['h2', 'h3']):
                        heading_text = heading.get_text().lower().strip()
                        if any(kw in heading_text for kw in ['see also', 'references', 'external links', 'further reading', 'bibliography', 'notes']):
                            for sibling in heading.find_next_siblings():
                                if sibling.name in ['h2', 'h3']:
                                    break
                                sibling.decompose()
                            heading.decompose()
                    
                    # Extract links from paragraphs only
                    for paragraph in parser_output.find_all('p', recursive=True):
                        for link in paragraph.find_all('a', href=True):
                            href = link['href']
                            if href.startswith('/wiki/') and ':' not in href:
                                from urllib.parse import unquote
                                page_title = unquote(href.replace('/wiki/', '').replace('_', ' '))
                                body_links.add(page_title)
    
    except Exception as e:
        print(f"Error parsing HTML for {title}: {e}")
        # If HTML parsing fails, fall back to using all links (less strict)
        body_links = None
    
    # Step 2: Use generator=links for all links with descriptions
    params = {
        "action": "query",
        "format": "json",
        "generator": "links",
        "titles": title,
        "gplnamespace": 0,
        "gpllimit": "max",
        "prop": "pageterms",
        "wbptterms": "description"
    }
    
    # Person keywords
    person_keywords = {
        "born", "died", "actor", "actress", "singer", "politician", "player", 
        "athlete", "musician", "writer", "director", "artist", "scientist", "philosopher", 
        "king", "queen", "prince", "princess", "emperor", "monarch", "president", 
        "minister", "businessman", "magnate", "inventor", "comedian", "rapper", 
        "producer", "author", "activist", "criminal", "victim", "judge", "lawyer", 
        "officer", "soldier", "pilot", "astronaut", "doctor", "physicist", "chemist", 
        "biologist", "mathematician", "engineer", "architect", "poet", "playwright"
    }
    
    # Exclude keywords
    exclude_keywords = {
        "film", "movie", "list", "index", "timeline", 
        "history", "category", "template", "book", "novel", "series", "show", "episode", 
        "game", "company", "organization", "team", "club", "place", "city", "country", 
        "war", "battle", "event", "ideology", "mythology", "fictional", "election", 
        "culture", "diaspora", "movement", "system", "theory", "policy", "act", 
        "law", "treaty", "case", "court", "party", "government", "state", "province", 
        "district", "county", "village", "town", "island", "mountain", "river", "lake", 
        "sea", "ocean", "bridge", "building", "structure", "station", "airport", "port"
    }
    
    try:
        while True:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    continue
                
                page_title = page_data.get("title", "")
                description = page_data.get("terms", {}).get("description", [""])[0].lower()
                title_lower = page_title.lower()
                
                # Filter 1: Must be in body paragraphs (if we successfully parsed HTML)
                if body_links is not None and page_title not in body_links:
                    continue
                
                # Filter 2: Person keywords check
                has_person_keyword = any(k in description for k in person_keywords)
                has_exclude_keyword = any(k in description for k in exclude_keywords) or \
                                      any(k in title_lower for k in exclude_keywords)
                
                # Filter 3: Bad title patterns
                is_bad_title = (title_lower.startswith("list of") or 
                                title_lower.startswith("index of") or 
                                title_lower.startswith("timeline of") or 
                                title_lower.startswith("history of") or
                                "(film)" in title_lower or
                                "(song)" in title_lower or
                                "(band)" in title_lower or
                                "(album)" in title_lower)
                
                # Accept if: has person keyword AND no exclude keyword AND not bad title
                if has_person_keyword and not has_exclude_keyword and not is_bad_title:
                    links.add(page_title)
            
            if "continue" not in data:
                break
            
            if "continue" in data and "gplcontinue" in data["continue"]:
                params["gplcontinue"] = data["continue"]["gplcontinue"]
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
    
    # Do NOT pop from path_end. 
    # visited_end[meeting_point] is the next node, so path_end starts with the node AFTER meeting_point.
        
    return path_start + path_end

import json
from typing import AsyncGenerator

async def find_shortest_path(start_page: str, end_page: str) -> AsyncGenerator[str, None]:
    """
    Finds the shortest path between two Wikipedia pages using Bi-directional BFS.
    Yields JSON strings representing status updates or the final result.
    """
    if start_page == end_page:
        yield json.dumps({"status": "finished", "path": [start_page]})
        return

    # Async client with limits to avoid overwhelming the API
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    headers = {
        "User-Agent": "WikiShortestPathBot/1.0 (http://example.com/bot; bot@example.com)"
    }
    async with httpx.AsyncClient(limits=limits, timeout=10.0, headers=headers) as client:
        # Queues for BFS
        queue_start = deque([start_page])
        queue_end = deque([end_page])

        # Visited sets keeping track of parents for path reconstruction
        visited_start: Dict[str, Optional[str]] = {start_page: None}
        visited_end: Dict[str, Optional[str]] = {end_page: None}
        
        yield json.dumps({"status": "info", "message": f"Initializing search from '{start_page}' to '{end_page}'..."})

        step_count = 0
        while queue_start and queue_end:
            step_count += 1
            
            # Expand the smaller queue to optimize search
            if len(queue_start) <= len(queue_end):
                current_node = queue_start.popleft()
                yield json.dumps({"status": "visiting", "node": current_node, "direction": "forward", "step": step_count})
                
                # Get forward links
                neighbors = await get_links(client, current_node)
                
                for neighbor in neighbors:
                    if neighbor in visited_end:
                        visited_start[neighbor] = current_node
                        path = reconstruct_path(visited_start, visited_end, neighbor)
                        yield json.dumps({"status": "finished", "path": path})
                        return
                    
                    if neighbor not in visited_start:
                        visited_start[neighbor] = current_node
                        queue_start.append(neighbor)
            else:
                current_node = queue_end.popleft()
                yield json.dumps({"status": "visiting", "node": current_node, "direction": "backward", "step": step_count})
                
                # Get backward links (pages that link to current_node)
                neighbors = await get_backlinks(client, current_node)
                
                for neighbor in neighbors:
                    if neighbor in visited_start:
                        visited_end[neighbor] = current_node
                        path = reconstruct_path(visited_start, visited_end, neighbor)
                        yield json.dumps({"status": "finished", "path": path})
                        return
                    
                    if neighbor not in visited_end:
                        visited_end[neighbor] = current_node
                        queue_end.append(neighbor)

    yield json.dumps({"status": "error", "message": "No path found."})
