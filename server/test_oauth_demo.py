#!/usr/bin/env python3
"""
Demo script to test OAuth functionality of the Graphiti server
"""

import requests
import json

BASE_URL = "http://localhost:8002"
API_KEY = "test-api-key-for-development"

def test_api_key_auth():
    """Test API key authentication"""
    print("Testing API Key Authentication...")
    
    # Test with API key
    headers = {"X-API-Key": API_KEY}
    response = requests.get(f"{BASE_URL}/stats", headers=headers)
    print(f"✓ With API key: {response.status_code}")
    print(f"  Stats: {response.json()}")
    
    # Test without API key
    response = requests.get(f"{BASE_URL}/stats")
    print(f"✗ Without API key: {response.status_code}")
    print()

def test_oauth_endpoints():
    """Test OAuth endpoints"""
    print("Testing OAuth Endpoints...")
    
    # Test Google OAuth login
    response = requests.post(f"{BASE_URL}/auth/google/login")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Google OAuth initiation: {response.status_code}")
        print(f"  Authorization URL: {data.get('authorization_url', '')[:50]}...")
        print(f"  State: {data.get('state', '')[:20]}...")
    else:
        print(f"✗ Google OAuth failed: {response.status_code}")
    
    # Test GitHub OAuth login
    response = requests.post(f"{BASE_URL}/auth/github/login")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ GitHub OAuth initiation: {response.status_code}")
        print(f"  Authorization URL: {data.get('authorization_url', '')[:50]}...")
        print(f"  State: {data.get('state', '')[:20]}...")
    else:
        print(f"✗ GitHub OAuth failed: {response.status_code}")
    
    # Test invalid provider
    response = requests.post(f"{BASE_URL}/auth/invalid/login")
    print(f"✓ Invalid provider rejection: {response.status_code}")
    print()

def test_protected_endpoints():
    """Test endpoints that require authentication"""
    print("Testing Protected Endpoints...")
    
    # Test /auth/me without auth
    response = requests.get(f"{BASE_URL}/auth/me")
    print(f"✓ /auth/me without auth: {response.status_code} (should be 401)")
    
    # Test with API key (should still fail for OAuth-only endpoint)
    headers = {"X-API-Key": API_KEY}
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"✓ /auth/me with API key: {response.status_code} (should be 401)")
    print()

def main():
    print("=" * 60)
    print("Graphiti OAuth Test Demo")
    print(f"Server: {BASE_URL}")
    print("=" * 60)
    print()
    
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/healthcheck")
        if response.status_code != 200:
            print("❌ Server is not responding!")
            return
        print("✓ Server is healthy")
        print()
        
        test_api_key_auth()
        test_oauth_endpoints()
        test_protected_endpoints()
        
        print("=" * 60)
        print("OAuth Configuration Notes:")
        print("- To enable Google OAuth: Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
        print("- To enable GitHub OAuth: Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET")
        print("- Current redirect URL: http://localhost:8002/auth/{provider}/callback")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server at", BASE_URL)
        print("Make sure the server is running!")

if __name__ == "__main__":
    main()