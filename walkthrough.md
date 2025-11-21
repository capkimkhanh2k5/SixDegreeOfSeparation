# Wikipedia Shortest Path Walkthrough

## Overview
I have implemented a Bi-directional BFS algorithm in Python to find the shortest path between two Wikipedia pages. The solution uses `httpx` for asynchronous API calls to ensure high performance.

## Implementation Details
- **File**: [wiki_shortest_path.py](file:///Users/capkimkhanh/Documents/6DegreeOfSeparation/wiki_shortest_path.py)
- **Algorithm**: Bi-directional Breadth-First Search (BFS).
- **Libraries**: `httpx` (async HTTP client), `asyncio`.
- **Features**:
    - Filters for Main namespace (ns=0).
    - Handles dead-ends and non-existent pages.
    - Optimizes by expanding the smaller frontier.

## Verification Results

### Test Case: Python to Philosophy
I ran the script with the start page "Python (programming language)" and end page "Philosophy".

**Command:**
```bash
./venv/bin/python wiki_shortest_path.py
```

**Output:**
```
Finding path from 'Python (programming language)' to 'Philosophy'...
Path found (3 steps):
Python (programming language) -> Tuple -> Philosophy
```

### How to Run
1.  **Install Dependencies**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install httpx
    ```

2.  **Run the Script**:
    ```bash
    python wiki_shortest_path.py
    ```

## Conclusion
The solution works as expected, correctly finding a short path between two loosely connected Wikipedia pages. The async implementation ensures efficient data fetching.
