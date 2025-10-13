#!/bin/bash

# Development script for Desktop Dog

echo "🐕 Starting Desktop Dog in development mode..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Build Electron main process
echo "🔨 Building Electron main process..."
npm run dev:electron &

# Wait a bit for the build
sleep 2

# Start Vite dev server
echo "🚀 Starting Vite dev server..."
npm run dev:react

wait

