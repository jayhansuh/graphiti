# Graphiti Production Deployment Guide

This guide helps you deploy the Graphiti API Playground to a production server.

## Prerequisites

- Ubuntu/Debian-based Linux server (tested on Amazon Linux 2023)
- Python 3.8+
- Docker (for Neo4j)
- Nginx
- Domain name or public IP address

## Quick Deploy Script

Use the provided deployment script for automated setup:

```bash
cd deployment
chmod +x deploy.sh
./deploy.sh
```

## Manual Deployment Steps

### 1. Install Dependencies

```bash
# Install system packages
sudo yum install -y nginx python3 python3-pip git docker
# Or for Ubuntu/Debian:
# sudo apt-get update && sudo apt-get install -y nginx python3 python3-pip git docker.io

# Install uv for Python package management
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 2. Set up Neo4j

```bash
# Start Neo4j container
sudo docker run -d \
  --name neo4j \
  --restart always \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password_here \
  -e NEO4J_PLUGINS='["apoc"]' \
  -v $HOME/neo4j/data:/data \
  neo4j:5.26.0
```

### 3. Configure Environment

```bash
# Create .env file in server directory
cd /path/to/graphiti/server
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key_here
NEO4J_PASSWORD=your_password_here
EOF
```

### 4. Install Python Dependencies

```bash
cd /path/to/graphiti/server
uv sync --extra dev
uv pip install gunicorn
```

### 5. Configure Nginx

```bash
# Copy and edit the nginx config
sudo cp nginx-graphiti.conf.example /etc/nginx/conf.d/graphiti.conf
sudo nano /etc/nginx/conf.d/graphiti.conf
# Update server_name with your domain

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Set up Systemd Service

```bash
# Copy and edit the service file
sudo cp graphiti.service.example /etc/systemd/system/graphiti.service
sudo nano /etc/systemd/system/graphiti.service
# Update paths and user information

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable graphiti
sudo systemctl start graphiti
```

### 7. Set up SSL (Optional)

For Let's Encrypt SSL (requires a domain name):
```bash
sudo yum install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

For self-signed certificate:
```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/graphiti.key \
  -out /etc/nginx/ssl/graphiti.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"
```

## Environment Variables

Create a `.env.example` file for reference:
```
OPENAI_API_KEY=sk-...
NEO4J_PASSWORD=your_secure_password
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
```

## Monitoring

Check service status:
```bash
sudo systemctl status graphiti
sudo journalctl -u graphiti -f  # Follow logs
```

Check Nginx logs:
```bash
sudo tail -f /var/log/nginx/graphiti_access.log
sudo tail -f /var/log/nginx/graphiti_error.log
```

## Troubleshooting

### Service won't start
- Check logs: `sudo journalctl -u graphiti -n 50`
- Verify Neo4j is running: `sudo docker ps | grep neo4j`
- Check permissions on working directory

### 502 Bad Gateway
- Ensure Graphiti service is running
- Check if port 8000 is listening: `sudo netstat -tlnp | grep 8000`
- Review Nginx error logs

### SSL Issues
- For EC2 instances, use Elastic Load Balancer for SSL termination
- Or use Cloudflare for SSL proxy
- Let's Encrypt doesn't work with EC2 public DNS names

## Security Considerations

1. Use strong passwords for Neo4j
2. Keep API keys in environment variables, never in code
3. Enable firewall rules to restrict access
4. Use HTTPS in production
5. Regularly update dependencies

## Backup

Backup Neo4j data:
```bash
sudo docker exec neo4j neo4j-admin database backup neo4j --to-path=/backups
sudo docker cp neo4j:/backups ./neo4j-backups
```