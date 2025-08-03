#!/usr/bin/env python3
"""Register documentation files to the knowledge base service."""

import json
import os
import sys
from pathlib import Path

import httpx

# Knowledge base API endpoint
KB_API_URL = "https://kb.agent-anywhere.com/api/documents"

# Documentation files to register
DOCS_DIR = Path(__file__).parent.parent / "docs" / "kb"
FILES_TO_REGISTER = [
    "tasks_history_20250103.md",
    "troubleshooting_20250103.md", 
    "key_lessons_20250103.md"
]


def register_document(file_path: Path, api_key: str) -> bool:
    """Register a single document to the knowledge base.
    
    Args:
        file_path: Path to the document file
        api_key: API key for the knowledge base service
        
    Returns:
        Success status
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Extract title from first line
        title = content.split('\n')[0].strip('# ')
        
        # Prepare document data
        doc_data = {
            "title": title,
            "content": content,
            "category": "graphiti-backup",
            "tags": ["graphiti", "backup", "s3", "documentation"],
            "source": f"graphiti/server/docs/kb/{file_path.name}",
            "metadata": {
                "project": "graphiti",
                "date": "2025-01-03",
                "author": "claude-code"
            }
        }
        
        # Send to API
        response = httpx.post(
            KB_API_URL,
            json=doc_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        if response.status_code == 200 or response.status_code == 201:
            print(f"✅ Successfully registered: {file_path.name}")
            return True
        else:
            print(f"❌ Failed to register {file_path.name}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error registering {file_path.name}: {e}")
        return False


def main():
    """Main registration process."""
    # Get API key from environment or command line
    api_key = os.getenv('KB_API_KEY')
    if not api_key and len(sys.argv) > 1:
        api_key = sys.argv[1]
        
    if not api_key:
        print("Error: Knowledge base API key required")
        print("Usage: KB_API_KEY=xxx python register_to_kb.py")
        print("   or: python register_to_kb.py YOUR_API_KEY")
        sys.exit(1)
        
    print(f"Registering documents to knowledge base at {KB_API_URL}...")
    print(f"Documents directory: {DOCS_DIR}")
    print()
    
    success_count = 0
    
    for file_name in FILES_TO_REGISTER:
        file_path = DOCS_DIR / file_name
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue
            
        if register_document(file_path, api_key):
            success_count += 1
            
    print()
    print(f"Summary: {success_count}/{len(FILES_TO_REGISTER)} documents registered successfully")
    
    if success_count < len(FILES_TO_REGISTER):
        sys.exit(1)


if __name__ == '__main__':
    main()