#!/bin/bash
# Graphiti Deployment Script
# This script automates the deployment of Graphiti API Playground

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables
GRAPHITI_USER=${GRAPHITI_USER:-$USER}
GRAPHITI_GROUP=${GRAPHITI_GROUP:-$USER}
GRAPHITI_PATH=${GRAPHITI_PATH:-$(pwd)/..}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-}
OPENAI_API_KEY=${OPENAI_API_KEY:-}
DOMAIN_NAME=${DOMAIN_NAME:-}

echo -e "${GREEN}Graphiti Deployment Script${NC}"
echo "=========================="
echo

# Function to prompt for input
prompt_input() {
    local var_name=$1
    local prompt_text=$2
    local is_password=$3
    
    if [ -z "${!var_name}" ]; then
        if [ "$is_password" = "true" ]; then
            read -s -p "$prompt_text: " value
            echo
        else
            read -p "$prompt_text: " value
        fi
        eval "$var_name='$value'"
    fi
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please don't run this script as root${NC}"
   exit 1
fi

# Gather configuration
echo "Configuration Setup"
echo "------------------"
prompt_input DOMAIN_NAME "Enter your domain name (or use 'localhost' for local deployment)"
prompt_input NEO4J_PASSWORD "Enter Neo4j password" true
prompt_input OPENAI_API_KEY "Enter OpenAI API key (or press Enter to add later)" true

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo -e "${RED}Cannot detect OS${NC}"
    exit 1
fi

echo
echo "Deployment Configuration:"
echo "- OS: $OS"
echo "- User: $GRAPHITI_USER"
echo "- Path: $GRAPHITI_PATH"
echo "- Domain: $DOMAIN_NAME"
echo

read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Install system dependencies
echo -e "\n${YELLOW}Installing system dependencies...${NC}"
if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
    sudo apt-get update
    sudo apt-get install -y nginx python3 python3-pip git docker.io
elif [[ "$OS" == "amzn" ]]; then
    sudo yum install -y nginx python3 python3-pip git docker
elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "fedora" ]]; then
    sudo yum install -y nginx python3 python3-pip git docker
else
    echo -e "${RED}Unsupported OS: $OS${NC}"
    exit 1
fi

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo -e "\n${YELLOW}Installing uv package manager...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Start Docker
echo -e "\n${YELLOW}Starting Docker service...${NC}"
sudo systemctl start docker
sudo systemctl enable docker

# Set up Neo4j
echo -e "\n${YELLOW}Setting up Neo4j...${NC}"
if ! sudo docker ps | grep -q neo4j; then
    sudo docker run -d \
        --name neo4j \
        --restart always \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/$NEO4J_PASSWORD \
        -e NEO4J_PLUGINS='["apoc"]' \
        -v $HOME/neo4j/data:/data \
        neo4j:5.26.0
    echo "Waiting for Neo4j to start..."
    sleep 30
else
    echo "Neo4j container already running"
fi

# Set up Python environment
echo -e "\n${YELLOW}Setting up Python environment...${NC}"
cd $GRAPHITI_PATH
uv sync --extra dev
uv pip install gunicorn

# Create .env file
echo -e "\n${YELLOW}Creating .env file...${NC}"
cat > .env << EOF
OPENAI_API_KEY=$OPENAI_API_KEY
NEO4J_PASSWORD=$NEO4J_PASSWORD
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
EOF

# Create log directory
sudo mkdir -p /var/log/graphiti
sudo chown $GRAPHITI_USER:$GRAPHITI_GROUP /var/log/graphiti

# Configure Nginx
echo -e "\n${YELLOW}Configuring Nginx...${NC}"
sudo cp deployment/nginx-graphiti.conf.example /etc/nginx/conf.d/graphiti.conf
sudo sed -i "s/your-domain.com/$DOMAIN_NAME/g" /etc/nginx/conf.d/graphiti.conf

# Configure systemd service
echo -e "\n${YELLOW}Setting up systemd service...${NC}"
sudo cp deployment/graphiti.service.example /etc/systemd/system/graphiti.service
sudo sed -i "s|YOUR_USER|$GRAPHITI_USER|g" /etc/systemd/system/graphiti.service
sudo sed -i "s|YOUR_GROUP|$GRAPHITI_GROUP|g" /etc/systemd/system/graphiti.service
sudo sed -i "s|/path/to/graphiti|$GRAPHITI_PATH|g" /etc/systemd/system/graphiti.service

# Start services
echo -e "\n${YELLOW}Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable graphiti
sudo systemctl start graphiti
sudo systemctl reload nginx

# Check service status
echo -e "\n${YELLOW}Checking service status...${NC}"
if systemctl is-active --quiet graphiti; then
    echo -e "${GREEN}✓ Graphiti service is running${NC}"
else
    echo -e "${RED}✗ Graphiti service failed to start${NC}"
    sudo journalctl -u graphiti -n 20
fi

# SSL setup prompt
echo -e "\n${YELLOW}SSL Setup${NC}"
if [ "$DOMAIN_NAME" != "localhost" ]; then
    read -p "Would you like to set up SSL with Let's Encrypt? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo yum install -y certbot python3-certbot-nginx || sudo apt-get install -y certbot python3-certbot-nginx
        sudo certbot --nginx -d $DOMAIN_NAME
    fi
fi

echo -e "\n${GREEN}Deployment complete!${NC}"
echo "====================
echo "Graphiti is now accessible at:"
echo "- HTTP: http://$DOMAIN_NAME/"
if [ "$DOMAIN_NAME" != "localhost" ]; then
    echo "- HTTPS: https://$DOMAIN_NAME/"
fi
echo
echo "Useful commands:"
echo "- Check status: sudo systemctl status graphiti"
echo "- View logs: sudo journalctl -u graphiti -f"
echo "- Restart service: sudo systemctl restart graphiti"
echo
echo "Next steps:"
echo "1. Test the API playground at http://$DOMAIN_NAME/"
echo "2. Configure firewall rules if needed"
echo "3. Set up monitoring and backups"