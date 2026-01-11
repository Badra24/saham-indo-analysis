#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Saham Indo Backend Launcher ===${NC}"

# Ensure we are in the backend directory
if [[ $(basename "$PWD") != "backend" ]]; then
    if [ -d "backend" ]; then
        cd backend
    else
        echo -e "${RED}Error: Could not find backend directory.${NC}"
        exit 1
    fi
fi

# Port Conflict Handling
PORT=8000
PID=$(lsof -ti:$PORT)
if [ ! -z "$PID" ]; then
    echo -e "${YELLOW}Port $PORT is being used by PID $PID. Killing it...${NC}"
    kill -9 $PID
    sleep 1
fi

# Fix broken venv
if [ -d ".venv" ]; then
    # Simple check if pip works
    if ! .venv/bin/pip --version > /dev/null 2>&1; then
        echo -e "${YELLOW}Virtual environment appears broken. Recreating...${NC}"
        rm -rf .venv
    fi
fi

# Create venv if missing
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies silently unless error
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! pip install -r requirements.txt > /dev/null 2>&1; then
    echo -e "${RED}Dependency installation failed. Trying with verbose output:${NC}"
    pip install -r requirements.txt
    exit 1
fi

echo -e "${GREEN}Starting Uvicorn Server...${NC}"
echo -e "Server will auto-reload on code changes."

# Start server
uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
