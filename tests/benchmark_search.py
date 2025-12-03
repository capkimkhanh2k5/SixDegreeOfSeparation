import asyncio
import sys
import os
import time
import json

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bfs import BidirectionalLevelBasedSearch
from backend.llm_client import generate_relationship_context

async def run_benchmark():
    start_node = "Ho Chi Minh"
    end_node = "Che Guevara"
    
    print(f"[MOCK OUTPUT]")
    print(f"> Search started...")
    print(f"> Exploring: {start_node} (Forward) | {end_node} (Backward)")
    
    searcher = BidirectionalLevelBasedSearch()
    
    start_time = time.time()
    path_found = False
    final_path = []
    total_nodes_visited = 0
    
    try:
        async for message in searcher.search(start_node, end_node):
            data = json.loads(message)
            
            if data["status"] == "exploring":
                stats = data.get("stats", {})
                total_nodes_visited = stats.get("visited", 0)
                # Optional: Print progress
                # print(f"> Visited: {total_nodes_visited} nodes...", end="\r")
                
            elif data["status"] == "finished":
                path_found = True
                final_path = data["path"]
                break
            elif data["status"] == "error":
                print(f"\nERROR: {data['message']}")
                break
            elif data["status"] == "not_found":
                print(f"\nPath not found.")
                break
                
    except Exception as e:
        print(f"\nEXCEPTION: {e}")
        
    end_time = time.time()
    duration = end_time - start_time
    
    if path_found:
        print(f"> PATH FOUND in {duration:.1f} seconds!")
        print(f"> Visited: {total_nodes_visited} nodes.")
        print(f"> ------------------------------------------------")
        
        # Enrich path with context
        enriched_path = []
        for i in range(len(final_path) - 1):
            p1 = final_path[i]
            p2 = final_path[i+1]
            context = await generate_relationship_context(p1, p2)
            enriched_path.append((p1, context))
        
        enriched_path.append((final_path[-1], None))
        
        for i, (node, context) in enumerate(enriched_path):
            print(f"> {i+1}. [{node}]")
            if context:
                print(f">    ⬇ (Context: {context})")
                
    else:
        print(f"> NO PATH FOUND in {duration:.1f} seconds.")
        print(f"> Visited: {total_nodes_visited} nodes.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
