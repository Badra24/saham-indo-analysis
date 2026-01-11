#!/bin/bash

# Ensure we are in the frontend directory
if [[ $(basename "$PWD") != "frontend" ]]; then
    if [ -d "frontend" ]; then
        cd frontend
    else
        echo "Error: Could not find frontend directory."
        exit 1
    fi
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
else
    echo "Dependencies already installed. Checking for updates..."
    npm install
fi

echo "Starting development server..."
npm run dev
