import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.bfs import find_shortest_path

async def run_test():
    print("Running reproduction test: Taylor Swift -> Ho Chi Minh")
    start_page = "Taylor Swift"
    end_page = "Ho Chi Minh"
    
    found_path = False
    path_result = []
    
    async for msg in find_shortest_path(start_page, end_page):
        print(msg)
        if "finished" in msg:
            import json
            data = json.loads(msg)
            if data.get("status") == "finished":
                found_path = True
                path_result = data.get("path", [])
                break
    
    if found_path:
        print(f"\nSUCCESS: Path found: {path_result}")
        # Verify if all nodes are likely people (simple check)
        # In a real test we might check against a list or use LLM to verify
        print("Please manually verify if these are all people.")
    else:
        print("\nFAILURE: No path found.")

if __name__ == "__main__":
    asyncio.run(run_test())
