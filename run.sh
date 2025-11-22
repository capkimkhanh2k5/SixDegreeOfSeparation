#!/bin/bash

# Function to kill background processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    exit
}

# Trap SIGINT (Ctrl+C)
trap cleanup SIGINT

echo "Building Frontend..."
cd frontend
npm run build
cd ..

echo "Starting Unified Server on Port 8000..."
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Wait is not needed as uvicorn runs in foreground now (or we can background it if preferred, but foreground is better for logs)
