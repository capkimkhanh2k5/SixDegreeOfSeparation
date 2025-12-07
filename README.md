<p align="center">
  <img src="assets/logo.png" alt="Six Degrees of Wikipedia" width="120">
</p>

<h1 align="center">🌐 Six Degrees of Wikipedia</h1>

<p align="center">
  <strong>Find the shortest path between any two people on Wikipedia</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#the-challenge">The Challenge</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#optimizations">Optimizations</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/status-production--ready-brightgreen.svg" alt="Status">
</p>

---

## ✨ Features

- 🔍 **Bidirectional BFS** - O(b^(d/2)) complexity for lightning-fast pathfinding
- 👤 **Person-Only Filtering** - 96% noise reduction using Wikipedia category analysis
- 🏛️ **Historical Figure Support** - Works with emperors, khans, pharaohs, and modern CEOs alike
- 💾 **Smart Caching** - Persistent cache for repeated searches
- 🎨 **Beautiful UI** - React frontend with real-time search visualization
- 🤖 **LLM Integration** - AI-generated relationship explanations

---

## 🎯 The Challenge

**Can we find a connection between Genghis Khan (12th century Mongol Emperor) and Elon Musk (21st century Tech CEO)?**

| Dimension | Challenge |
|-----------|-----------|
| **Time Gap** | ~800 years |
| **Domain Gap** | Military Conqueror ↔ Technology Entrepreneur |
| **Super-node Risk** | Genghis Khan has 1000+ Wikipedia links |

### Results

```
Genghis Khan: 586 links → 569 (filtered) → 52 humans (91% reduction)
Elon Musk:    2500 links → 2281 (filtered) → 101 humans (96% reduction)
```

The algorithm successfully navigates through centuries of history to find valid human-to-human connections!

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, FastAPI, asyncio |
| **Frontend** | React, Vite, TailwindCSS |
| **APIs** | Wikipedia MediaWiki API, Google Gemini |
| **Algorithm** | Bidirectional BFS with parent-pointer optimization |

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/capkimkhanh2k5/SixDegreeOfSeparation.git
cd SixDegreeOfSeparation

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Gemini API key (optional, for LLM features)

# Build frontend
cd frontend
npm install
npm run build
cd ..
```

---

## 🚀 Usage

### Start the Server

```bash
# Run the full application
./run.sh

# Or manually:
uvicorn backend.main:app --reload --port 8000
```

Visit `http://localhost:8000` in your browser.

### Run Benchmarks

```bash
# Standard benchmark
python tests/benchmark_search.py

# Extreme test (Genghis Khan → Elon Musk)
python tests/extreme_benchmark.py
```

---

## ⚡ Optimizations

### 1. Bidirectional BFS

Instead of searching from start to end (complexity O(b^d)), we search from **both directions** simultaneously and meet in the middle.

```
Standard BFS:       O(b^d)
Bidirectional BFS:  O(b^(d/2))
```

For a path of depth 6 with branching factor 100:
- Standard: 100^6 = 1 trillion nodes
- Bidirectional: 2 × 100^3 = 2 million nodes (500,000x faster!)

### 2. Parent-Pointer Path Reconstruction

Instead of storing full paths for every node:

```python
# Before (memory-intensive)
visited = {"Node A": ["Start", "X", "Y", "Node A"]}  # O(n × d) memory

# After (memory-efficient)
parent = {"Node A": "Y", "Y": "X", "X": "Start"}  # O(n) memory
```

**Result:** ~8x memory reduction for deep searches.

### 3. Strict Person Filtering

Two-stage filter using Wikipedia categories:

**Stage 1 - Negative Filter** (exclude non-humans):
- Animals, fictional characters, places, events, organizations

**Stage 2 - Positive Filter** (confirm humans):
- "Living people", "1990 births", "Monarchs", "Politicians", etc.

```python
PERSON_POSITIVE_KEYWORDS = [
    # Modern
    "living people", "actors", "politicians", "scientists",
    # Historical (critical for Genghis Khan!)
    "emperors", "monarchs", "khans", "sultans", "generals",
]
```

### 4. Multi-Layer Caching

| Cache | Purpose | Reduction |
|-------|---------|-----------|
| **Page Cache** | Store page links | Avoid re-fetching |
| **Category Cache** | Human/non-human decisions | 90%+ API reduction |
| **Backlink Cache** | Incoming links | Popular target optimization |

---

## 📊 Algorithm Visualization

```
     START: Genghis Khan                    END: Elon Musk
              │                                    │
              ▼                                    ▼
    ┌─────────────────┐                 ┌─────────────────┐
    │ Forward Queue   │                 │ Backward Queue  │
    │ (expand smaller)│◄───────────────►│ (expand smaller)│
    └─────────────────┘                 └─────────────────┘
              │                                    │
              ▼                                    ▼
    ┌─────────────────┐                 ┌─────────────────┐
    │ Fetch Links     │                 │ Fetch Backlinks │
    │ (586 raw)       │                 │ (2500 raw)      │
    └─────────────────┘                 └─────────────────┘
              │                                    │
              ▼                                    ▼
    ┌─────────────────┐                 ┌─────────────────┐
    │ Heuristic Filter│                 │ Heuristic Filter│
    │ (569 remaining) │                 │ (2281 remaining)│
    └─────────────────┘                 └─────────────────┘
              │                                    │
              ▼                                    ▼
    ┌─────────────────┐                 ┌─────────────────┐
    │ Category Check  │                 │ Category Check  │
    │ (52 humans!)    │                 │ (101 humans!)   │
    └─────────────────┘                 └─────────────────┘
              │                                    │
              └───────────────┬───────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ INTERSECTION!   │
                    │ Path Found! 🎉  │
                    └─────────────────┘
```

---

## 📁 Project Structure

```
SixDegreeOfSeparation/
├── backend/
│   ├── bfs.py          # Core bidirectional BFS engine
│   ├── main.py         # FastAPI application
│   ├── llm_client.py   # Gemini AI integration
│   └── text_utils.py   # Name resolution utilities
├── frontend/
│   ├── src/            # React components
│   └── dist/           # Production build
├── tests/
│   ├── benchmark_search.py
│   └── extreme_benchmark.py
├── wiki_cache.json     # Persistent page cache
├── category_cache.json # Person detection cache
└── requirements.txt
```

---

## 🙏 Acknowledgments

- [Wikipedia API](https://www.mediawiki.org/wiki/API:Main_page) for providing the data
- [Google Gemini](https://ai.google.dev/) for relationship explanations
- Inspired by the [Six Degrees of Kevin Bacon](https://en.wikipedia.org/wiki/Six_Degrees_of_Kevin_Bacon) game

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/capkimkhanh2k5">capkimkhanh2k5</a>
</p>
