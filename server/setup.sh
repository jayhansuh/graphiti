#!/bin/bash
# Graphiti Server Setup Script
# This script sets up the development environment for Graphiti server

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Graphiti Server Setup Script${NC}"
echo "============================"
echo

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}Error: Python $required_version or higher is required. Found: $python_version${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $python_version${NC}"

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo -e "\n${YELLOW}Installing uv package manager...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
else
    echo -e "${GREEN}✓ uv is already installed${NC}"
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    uv venv
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
echo "This will install:"
echo "  - Core dependencies (FastAPI, Graphiti, etc.)"
echo "  - Development dependencies (pytest, ruff, pyright)"
echo "  - Production server (gunicorn)"
echo

# Install core and dev dependencies
uv sync --extra dev

# Install production server
echo -e "\n${YELLOW}Installing production server...${NC}"
uv pip install gunicorn

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "\n${YELLOW}Creating .env file from template...${NC}"
    if [ -f "deployment/.env.example" ]; then
        cp deployment/.env.example .env
        echo -e "${YELLOW}Please edit .env and add your configuration:${NC}"
        echo "  - OPENAI_API_KEY"
        echo "  - NEO4J_PASSWORD"
    else
        cat > .env << EOF
# Graphiti Environment Configuration
OPENAI_API_KEY=your-api-key-here
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
EOF
        echo -e "${YELLOW}Created .env file. Please add your API keys and passwords.${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Create necessary directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p static/css static/js static/images
echo -e "${GREEN}✓ Static directories created${NC}"

# Check if Neo4j is running
echo -e "\n${YELLOW}Checking Neo4j status...${NC}"
if command -v docker &> /dev/null; then
    if docker ps | grep -q neo4j; then
        echo -e "${GREEN}✓ Neo4j is running${NC}"
    else
        echo -e "${YELLOW}Neo4j is not running. To start it:${NC}"
        echo "docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5.26.0"
    fi
else
    echo -e "${YELLOW}Docker not found. Please install Docker to run Neo4j.${NC}"
fi

echo -e "\n${GREEN}Setup complete!${NC}"
echo
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Start Neo4j if not running"
echo "3. Activate virtual environment: source .venv/bin/activate"
echo "4. Run development server: uvicorn graph_service.main:app --reload"
echo "5. Or run production server: gunicorn graph_service.main:app -w 2 -k uvicorn.workers.UvicornWorker"
echo
echo "For full deployment instructions, see deployment/README.md"