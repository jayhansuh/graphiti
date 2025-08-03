#!/usr/bin/env python3
"""
Test script to verify authentication flow on https://kb.agent-anywhere.com/

Tests:
1. Automatic redirect to login page when not authenticated
2. API key login functionality
3. Stats display when authenticated
4. Session persistence
"""

import requests
import json
from typing import Dict, Optional

# Test configuration
BASE_URL = "https://kb.agent-anywhere.com"
API_KEY = "gGiC5I-xoEXuM1AXpPvaV1H82AFTGfadDjLiUq2D1fc"

class AuthTester:
    def __init__(self):
        self.session = requests.Session()
        
    def test_unauthenticated_redirect(self) -> bool:
        """Test 1: Verify unauthenticated users are redirected to login"""
        print("\n[TEST 1] Testing unauthenticated redirect...")
        
        # Clear any existing cookies/headers
        self.session.cookies.clear()
        self.session.headers.clear()
        
        try:
            # Try to access the main page without auth
            response = self.session.get(f"{BASE_URL}/", allow_redirects=False)
            
            # Check if we get a redirect
            if response.status_code == 302 or response.status_code == 301:
                redirect_location = response.headers.get('Location', '')
                print(f"✓ Got redirect: {redirect_location}")
                return 'login' in redirect_location
            elif response.status_code == 200:
                # Check if the page contains redirect JavaScript
                if 'window.location.href = \'/login' in response.text:
                    print("✓ Page contains JavaScript redirect to login")
                    return True
                else:
                    print("✗ Page loaded without authentication check")
                    return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    def test_api_key_login(self) -> bool:
        """Test 2: Verify API key login works"""
        print("\n[TEST 2] Testing API key login...")
        
        try:
            # Test stats endpoint with API key
            headers = {"X-API-Key": API_KEY}
            response = self.session.get(f"{BASE_URL}/stats", headers=headers)
            
            if response.status_code == 200:
                stats = response.json()
                print(f"✓ API key authentication successful")
                print(f"  Stats: {stats}")
                return True
            else:
                print(f"✗ API key authentication failed: {response.status_code}")
                print(f"  Response: {response.text}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    def test_stats_display(self) -> bool:
        """Test 3: Verify stats are displayed when authenticated"""
        print("\n[TEST 3] Testing stats display with authentication...")
        
        try:
            # Get stats with API key
            headers = {"X-API-Key": API_KEY}
            response = self.session.get(f"{BASE_URL}/stats", headers=headers)
            
            if response.status_code == 200:
                stats = response.json()
                # Verify we have the expected fields
                required_fields = ['entity_count', 'episode_count', 'relation_count']
                has_all_fields = all(field in stats for field in required_fields)
                
                if has_all_fields:
                    print(f"✓ Stats retrieved successfully:")
                    print(f"  Entities: {stats['entity_count']}")
                    print(f"  Episodes: {stats['episode_count']}")
                    print(f"  Relations: {stats['relation_count']}")
                    return True
                else:
                    print(f"✗ Stats response missing fields: {stats}")
                    return False
            else:
                print(f"✗ Failed to get stats: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    def test_protected_endpoints(self) -> bool:
        """Test 4: Verify other endpoints require authentication"""
        print("\n[TEST 4] Testing protected endpoints...")
        
        endpoints = [
            ("/graph-data", "GET"),
            ("/episodes/test-group", "GET"),
            ("/search", "POST"),
        ]
        
        all_protected = True
        
        for endpoint, method in endpoints:
            # Test without auth
            if method == "GET":
                response = self.session.get(f"{BASE_URL}{endpoint}")
            else:
                response = self.session.post(f"{BASE_URL}{endpoint}", 
                                           json={"query": "test"})
            
            if response.status_code == 401:
                print(f"✓ {endpoint} is protected (401 without auth)")
            else:
                print(f"✗ {endpoint} not protected! Status: {response.status_code}")
                all_protected = False
            
            # Test with auth
            headers = {"X-API-Key": API_KEY}
            if method == "GET":
                response_auth = self.session.get(f"{BASE_URL}{endpoint}", 
                                               headers=headers)
            else:
                headers["Content-Type"] = "application/json"
                response_auth = self.session.post(f"{BASE_URL}{endpoint}", 
                                                 headers=headers,
                                                 json={"query": "test"})
            
            if response_auth.status_code in [200, 400, 404]:
                print(f"  ✓ {endpoint} accessible with auth")
            else:
                print(f"  ✗ {endpoint} still blocked with auth: {response_auth.status_code}")
        
        return all_protected
    
    def test_github_oauth_consideration(self) -> bool:
        """Test 5: Check if OAuth endpoints are configured"""
        print("\n[TEST 5] Checking OAuth configuration...")
        
        try:
            # Check if OAuth login endpoints exist
            response = self.session.post(f"{BASE_URL}/auth/github/login")
            
            if response.status_code == 400 and "not configured" in response.text:
                print("✓ GitHub OAuth endpoint exists but not configured")
                print("  This would have the same auth issues as API key")
                return True
            elif response.status_code == 200:
                oauth_data = response.json()
                if 'authorization_url' in oauth_data:
                    print("✓ GitHub OAuth is configured")
                    print(f"  Auth URL: {oauth_data['authorization_url'][:50]}...")
                    return True
            else:
                print(f"? OAuth endpoint status: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Error checking OAuth: {e}")
            return False

def main():
    """Run all authentication tests"""
    print("=" * 60)
    print("Testing Graphiti Authentication Flow")
    print(f"Target: {BASE_URL}")
    print("=" * 60)
    
    tester = AuthTester()
    
    tests = [
        ("Unauthenticated Redirect", tester.test_unauthenticated_redirect),
        ("API Key Login", tester.test_api_key_login),
        ("Stats Display", tester.test_stats_display),
        ("Protected Endpoints", tester.test_protected_endpoints),
        ("OAuth Configuration", tester.test_github_oauth_consideration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All authentication tests passed!")
    else:
        print("\n❌ Some tests failed - authentication needs fixing")
    
    return passed == total

if __name__ == "__main__":
    exit(0 if main() else 1)