import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.bfs import BFS_Search

class TestHeuristics(unittest.TestCase):
    def setUp(self):
        # Mock client not needed for heuristic_filter
        self.bfs = BFS_Search("Start", "End", None)

    def test_heuristic_filter(self):
        candidates = [
            "Taylor Swift",
            "1989 (Taylor Swift album)",
            "Ho Chi Minh City",
            "Barack Obama",
            "List of awards received by Taylor Swift",
            "Vietnam War",
            "Henry Kissinger",
            "Republic of Vietnam",
            "2024 United States presidential election",
            "John F. Kennedy",
            "Kennedy family", # Might be tricky, but usually we want specific people
            "The Eras Tour",
            # "Shake It Off", # Hard to catch with heuristics, relies on LLM
            "Nguyen Van Thieu"
        ]
        
        expected_kept = [
            "Taylor Swift",
            "Barack Obama",
            "Henry Kissinger",
            "John F. Kennedy",
            "Nguyen Van Thieu"
            # "Kennedy family" - debatable, but often treated as a group/topic
        ]
        
        filtered = self.bfs.heuristic_filter(candidates)
        
        print("\nFiltered Candidates:")
        for c in filtered:
            print(f" - {c}")
            
        for item in expected_kept:
            self.assertIn(item, filtered, f"Should keep {item}")
            
        for item in candidates:
            if item not in expected_kept and item != "Kennedy family": # Allow family for now if not strictly excluded
                self.assertNotIn(item, filtered, f"Should exclude {item}")

if __name__ == '__main__':
    unittest.main()
