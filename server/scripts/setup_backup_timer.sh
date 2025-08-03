#!/bin/bash
# Setup script for Graphiti backup systemd timer

set -e

echo "Setting up Graphiti backup systemd timer..."

# Copy service files to systemd directory
sudo cp /home/ec2-user/graphiti/server/systemd/graphiti-backup.service /etc/systemd/system/
sudo cp /home/ec2-user/graphiti/server/systemd/graphiti-backup.timer /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable graphiti-backup.timer
sudo systemctl start graphiti-backup.timer

# Check status
echo ""
echo "Timer status:"
sudo systemctl status graphiti-backup.timer --no-pager

echo ""
echo "Next scheduled run:"
sudo systemctl list-timers graphiti-backup.timer --no-pager

echo ""
echo "Setup complete! The backup will run daily at 2 AM UTC."
echo "To run a backup immediately: sudo systemctl start graphiti-backup.service"
echo "To check backup logs: sudo journalctl -u graphiti-backup.service"