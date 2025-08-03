#!/bin/bash
# Deployment script for Graphiti server

set -e

echo "🚀 Deploying Graphiti server..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
echo "Running database migrations..."
alembic upgrade head 2>/dev/null || echo "No migrations to run"

# Generate JWT secret if not set
if [ -z "$JWT_SECRET_KEY" ]; then
    export JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "Generated JWT_SECRET_KEY: $JWT_SECRET_KEY"
fi

# Start the server
echo "Starting Graphiti server..."

# For development/testing
if [ "$ENV" = "development" ]; then
    uvicorn graph_service.main:app --reload --host 0.0.0.0 --port ${PORT:-8000}
else
    # For production with multiple workers
    gunicorn graph_service.main:app \
        --worker-class uvicorn.workers.UvicornWorker \
        --workers ${WORKERS:-4} \
        --bind ${HOST:-0.0.0.0}:${PORT:-8000} \
        --access-logfile - \
        --error-logfile - \
        --log-level info
fi