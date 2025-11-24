import asyncio
import sys
import os
import httpx

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bfs import LevelBasedSearch
from backend.llm_client import verify_candidates_with_llm

async def verify_logic_for_subject(subject_name: str):
    print(f"\n=== Verifying Connections for: {subject_name} ===\n")
    
    # Initialize Searcher (just to use its helper methods)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        searcher = LevelBasedSearch(subject_name, "Target Does Not Matter", client)
        
        # 1. Fetch Page Data
        print(f"1. Fetching Wikipedia Data for '{subject_name}'...")
        try:
            wiki_text, candidates = await searcher.get_page_data(subject_name)
            print(f"   -> Success! Fetched {len(wiki_text)} chars of text.")
            print(f"   -> Found {len(candidates)} raw links/candidates.")
        except Exception as e:
            print(f"   -> Error fetching data: {e}")
            return

        # 2. Heuristic Filtering
        print(f"\n2. Applying Heuristic Filter...")
        filtered_candidates = searcher.heuristic_filter(candidates)
        print(f"   -> Filtered down to {len(filtered_candidates)} candidates.")
        print(f"   -> Top 10 Filtered (Before LLM): {filtered_candidates[:10]}")

        # 3. LLM Verification
        print(f"\n3. Running LLM Verification (Top 50 candidates)...")
        candidates_to_verify = filtered_candidates[:50]
        
        verified_objs = await verify_candidates_with_llm(
            wiki_text, 
            subject_name, 
            target_name="Target Does Not Matter", # Target doesn't matter for 1st level verification
            candidates=candidates_to_verify
        )
        
        print(f"\n=== FINAL REPORT: Verified Connections ===")
        print(f"LLM Verified {len(verified_objs)} people out of {len(candidates_to_verify)} checked.\n")
        
        for i, obj in enumerate(verified_objs, 1):
            print(f"{i}. {obj['name']}")
            
        print("\n=== End of Report ===")

if __name__ == "__main__":
    asyncio.run(verify_logic_for_subject("Taylor Swift"))
