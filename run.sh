#!/bin/bash

# Function to kill background processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    exit
}

# Trap SIGINT (Ctrl+C)
trap cleanup SIGINT

echo "Starting Backend..."
source venv/bin/activate
uvicorn backend.main:app --reload --port 8001 &

echo "Starting Frontend..."
cd frontend
npm run dev &

# Wait for all background processes
wait
