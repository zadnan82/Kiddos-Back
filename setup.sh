#!/bin/bash

# Kiddos - Quick Setup Script
# This script sets up the development environment

set -e

echo "🎓 Setting up Kiddos - AI Educational Content Platform"
echo "=================================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    
    # Generate secure keys
    echo "🔐 Generating secure keys..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    ENCRYPTION_KEY=$(python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
    
    # Replace placeholder values
    sed -i "s/your-super-secret-jwt-key-change-this-in-production-min-32-chars/$SECRET_KEY/g" .env
    sed -i "s/your-base64-encoded-32-byte-encryption-key-for-pii-data/$ENCRYPTION_KEY/g" .env
    
    echo "✅ .env file created with secure keys"
    echo "⚠️  IMPORTANT: Add your Claude API key and Stripe keys to .env file"
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p uploads
mkdir -p scripts

# Create database initialization script
cat > scripts/init-db.sql << EOF
-- Kiddos Database Initialization
-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set timezone
SET timezone = 'UTC';
EOF

# Create nginx configuration for production
mkdir -p nginx
cat > nginx/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    server {
        listen 80;
        server_name localhost;
        
        location / {
            proxy_pass http://api;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
}
EOF

echo "🐳 Building Docker containers..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d db redis

echo "⏳ Waiting for database to be ready..."
sleep 10

echo "🗄️  Running database migrations..."
docker-compose run --rm api alembic upgrade head

echo "✨ Starting all services..."
docker-compose up -d

echo ""
echo "🎉 Kiddos is now running!"
echo ""
echo "📊 Services:"
echo "   • API Documentation: http://localhost:8000/docs"
echo "   • API Health Check:  http://localhost:8000/health"
echo "   • Flower (Tasks):     http://localhost:5555"
echo "   • Database:           localhost:5432"
echo "   • Redis:              localhost:6379"
echo ""
echo "📝 Next steps:"
echo "   1. Add your Claude API key to .env file"
echo "   2. Add your Stripe keys to .env file"
echo "   3. Restart services: docker-compose restart"
echo "   4. Test API: curl http://localhost:8000/health"
echo ""
echo "🔧 Useful commands:"
echo "   • View logs:      docker-compose logs -f"
echo "   • Stop services:  docker-compose down"
echo "   • Restart:        docker-compose restart"
echo "   • Shell access:   docker-compose exec api bash"
echo ""
echo "📚 Documentation: http://localhost:8000/docs"
echo ""

# Check if services are running
echo "🔍 Checking service health..."
sleep 5

if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ API is healthy"
else
    echo "⚠️  API might still be starting up. Check logs with: docker-compose logs api"
fi

if curl -s http://localhost:5555 > /dev/null; then
    echo "✅ Flower is running"
else
    echo "⚠️  Flower might still be starting up"
fi

echo ""
echo "🎓 Kiddos setup complete! Happy coding! 🚀"