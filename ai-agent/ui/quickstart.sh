#!/bin/bash
# Quick start script for Bot MVP (Linux/Mac)
# This script will start both API and Web servers

echo ""
echo "===================================================="
echo "  Bot MVP - Quick Start"
echo "===================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found!"
    echo "Please create .env file with ANTHROPIC_API_KEY and other settings"
    exit 1
fi

# Install requirements if needed
echo "Checking dependencies..."
python3 -m pip list | grep -q fastapi
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip install -r requirements.txt
fi

# Kill existing processes on ports 8100 and 8080 if they exist
echo "Cleaning up old processes..."

# For macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    lsof -ti:8100 | xargs kill -9 2>/dev/null
    lsof -ti:8080 | xargs kill -9 2>/dev/null
# For Linux
else
    fuser -k 8100/tcp 2>/dev/null
    fuser -k 8080/tcp 2>/dev/null
fi

echo ""

# Function to handle Ctrl+C to kill both servers
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $API_PID $WEB_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT

# Start API server in background
echo "Starting API Server (port 8100)..."
python3 api.py &
API_PID=$!
sleep 2

# Start Web server in background
echo "Starting Web Server (port 8080)..."
python3 web_server.py &
WEB_PID=$!
sleep 2

echo ""
echo "===================================================="
echo "  Servers started successfully!"
echo "===================================================="
echo ""
echo "URLs:"
echo "  Chat:      http://localhost:8080/index.html"
echo "  API Docs:  http://localhost:8100/docs"
echo "  Stats:     http://localhost:8080/stats.html"
echo "  Admin:     http://localhost:8080/admin.html"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for both processes
wait
