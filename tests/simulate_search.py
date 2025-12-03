import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bfs import find_shortest_path

async def main():
    start_page = "Ho Chi Minh"
    end_page = "Donald Trump"
    
    print(f"Starting simulation: {start_page} -> {end_page}")
    
    try:
        async for message in find_shortest_path(start_page, end_page):
            data = json.loads(message)
            if data["status"] == "visiting":
                print(f"[{data['direction'].upper()}] Visiting: {data['node']} (Step {data['step']}) - Found {data.get('found_count', '?')} children")
            elif data["status"] == "finished":
                print(f"\nSUCCESS! Path found: {data['path']}")
                break
            elif data["status"] == "error":
                print(f"\nERROR: {data['message']}")
            elif data["status"] == "info":
                print(f"INFO: {data['message']}")
                
    except Exception as e:
        print(f"Simulation Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
