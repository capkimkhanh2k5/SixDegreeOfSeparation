import asyncio
import httpx
from backend.bfs import BFS_Search
from dotenv import load_dotenv
import os

load_dotenv()

async def run_debug():
    start_page = "Taylor Swift"
    end_page = "Ho Chi Minh"
    
    print(f"--- DEBUGGING BFS: {start_page} -> {end_page} ---")
    
    headers = {
        "User-Agent": "SixDegreesOfWikipedia/1.0 (https://github.com/capkimkhanh2k5/SixDegreeOfSeparation; contact@example.com)"
    }
    
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        searcher = BFS_Search(start_page, end_page, client)
        
        async for msg in searcher.search():
            print(msg)

if __name__ == "__main__":
    asyncio.run(run_debug())
