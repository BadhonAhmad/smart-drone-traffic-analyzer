#!/bin/bash
echo "Starting Smart Drone Traffic Analyzer..."
echo ""
echo "Starting FastAPI backend on port 8000..."
python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
echo ""
echo "Starting Next.js frontend on port 3000..."
cd ../frontend && npm run dev &
FRONTEND_PID=$!
echo ""
echo "App running at http://localhost:3000"
echo "Press Ctrl+C to stop both servers."
wait
