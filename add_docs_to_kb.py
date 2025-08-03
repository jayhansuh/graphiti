#!/usr/bin/env python3
"""Script to add documentation files to Graphiti knowledge base"""

import json
import requests
from datetime import datetime
from pathlib import Path

# Configuration
KB_URL = "https://kb.agent-anywhere.com"
DOCS_DIR = Path("/home/ec2-user/graphiti/docs")

# Files to add
FILES_TO_ADD = [
    {
        "file": "2025-01-03-tasks.md",
        "name": "2025-01-03-tasks",
        "description": "Task history documentation - Work completed on Graphiti project"
    },
    {
        "file": "2025-01-03-troubleshooting.md", 
        "name": "2025-01-03-troubleshooting",
        "description": "Troubleshooting guide - MCP configuration issues and solutions"
    },
    {
        "file": "2025-01-03-key-lessons.md",
        "name": "2025-01-03-key-lessons",
        "description": "Key lessons learned - Collaboration insights and best practices"
    }
]

def add_document_to_kb(file_path: Path, name: str, description: str):
    """Add a single document to the knowledge base"""
    
    # Read file content
    content = file_path.read_text()
    
    # Create message payload
    payload = {
        "group_id": "graphiti-documentation",
        "messages": [
            {
                "content": content,
                "name": name,
                "role_type": "system",
                "role": "documentation",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source_description": description
            }
        ]
    }
    
    # Send request
    response = requests.post(
        f"{KB_URL}/messages",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    return response

def main():
    """Main function to add all documents"""
    print(f"Adding documentation files to Graphiti knowledge base at {KB_URL}")
    print("-" * 60)
    
    for file_info in FILES_TO_ADD:
        file_path = DOCS_DIR / file_info["file"]
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            continue
            
        print(f"\nAdding: {file_info['name']}")
        print(f"File: {file_path}")
        print(f"Description: {file_info['description']}")
        
        try:
            response = add_document_to_kb(
                file_path=file_path,
                name=file_info["name"],
                description=file_info["description"]
            )
            
            if response.status_code == 202:
                print(f"✅ Successfully queued for processing")
                result = response.json()
                print(f"   Response: {result}")
            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "-" * 60)
    print("Done!")

if __name__ == "__main__":
    main()