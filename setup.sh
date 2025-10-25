#!/bin/bash

# Bike Surface AI - Quick Start Script
# This script sets up the cloud infrastructure

set -e

echo "=================================="
echo "Bike Surface AI - Quick Setup"
echo "=================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Please install Docker first:"
    echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "  sudo sh get-docker.sh"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed!"
    echo "Please install Docker Compose plugin"
    exit 1
fi

echo "✓ Docker and Docker Compose found"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    
    # Generate random password
    DB_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-16)
    
    # Update .env file (works on Linux/Mac/Windows Git Bash)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/your_secure_password_here/$DB_PASSWORD/g" .env
    else
        # Linux/Windows Git Bash
        sed -i "s/your_secure_password_here/$DB_PASSWORD/g" .env
    fi
    
    echo "✓ Generated .env file with random database password"
else
    echo "✓ .env file already exists"
fi

echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p edge/models
mkdir -p edge/local_backups
mkdir -p training/models
mkdir -p training/datasets
echo "✓ Directories created"
echo ""

# Start Docker services
echo "🚀 Starting Docker services..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "🔍 Testing API health..."
sleep 5

if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✓ API is healthy"
else
    echo "⚠️  API health check failed (might take a few more seconds to start)"
fi

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "🌐 Web Interface: http://localhost"
echo "🔌 API Endpoint:  http://localhost:8000"
echo "🗄️  Database:      localhost:5432"
echo ""
echo "📖 Next steps:"
echo "   1. Open http://localhost in your browser"
echo "   2. Setup edge device (see SETUP.md)"
echo "   3. Train or deploy model"
echo ""
echo "📝 View logs: docker compose logs -f"
echo "🛑 Stop services: docker compose down"
echo ""
