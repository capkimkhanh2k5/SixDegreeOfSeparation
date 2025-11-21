# Six Degrees of Wikipedia

A web application that finds the shortest path between two Wikipedia pages using Bi-directional Breadth-First Search (BFS).

## Features
- **Bi-directional BFS**: Efficiently finds the shortest path by searching from both ends.
- **Async API Calls**: Uses `httpx` for fast, concurrent Wikipedia API requests.
- **Modern UI**: React + Tailwind CSS with dark mode, autocomplete, and animations.
- **Interactive Visualization**: Displays the path as a vertical timeline.

## Tech Stack
- **Backend**: Python, FastAPI, Uvicorn, httpx
- **Frontend**: React, Vite, Tailwind CSS

## Installation & Running

### Prerequisites
- Python 3.8+
- Node.js 16+

### 1. Backend Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn httpx

# Run the server
uvicorn backend.main:app --reload --port 8001
```
The API will be available at `http://127.0.0.1:8001`.

### 2. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```
The app will be available at `http://localhost:5173`.

## Usage
1. Enter a **Start Person/Page** (e.g., "Kevin Bacon").
2. Enter a **Target Person/Page** (e.g., "Barack Obama").
3. Click **Find Path**.
4. Watch the spinner while the algorithm searches.
5. View the shortest path connecting the two pages!

## License
MIT
