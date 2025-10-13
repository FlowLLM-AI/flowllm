#!/bin/bash

# Build script for Desktop Dog

echo "🐕 Building Desktop Dog..."

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build Electron and Vite
echo "🔨 Building application..."
npm run build

echo "✅ Build complete! Run 'npm start' to launch the app."

