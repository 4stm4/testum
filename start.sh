#!/bin/bash
# Quick Start Script for Ocultum

set -e

echo "🔐 Ocultum - Quick Start Script"
echo "================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and set FERNET_KEY before continuing!"
    echo "   Generate key with: make generate-key"
    exit 1
fi

# Check if FERNET_KEY is set
if grep -q "your-fernet-key" .env; then
    echo "⚠️  Warning: FERNET_KEY not set in .env file!"
    echo "   Generate key with: make generate-key"
    exit 1
fi

echo "🏗️  Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

echo "🗄️  Running database migrations..."
docker-compose exec -T app alembic upgrade head

echo ""
echo "✅ Ocultum is ready!"
echo ""
echo "📍 Access points:"
echo "   Web UI:        http://localhost:8000"
echo "   API:           http://localhost:8000/api/"
echo "   Health Check:  http://localhost:8000/health"
echo "   MinIO Console: http://localhost:9001 (admin: minioadmin / minioadmin)"
echo ""
echo "📖 View logs:     make logs"
echo "🛑 Stop services: make down"
echo "🧪 Run tests:     make test"
echo ""
echo "Happy deploying! 🎉"
