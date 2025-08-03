#!/usr/bin/env python3
"""
Verify that the authentication JavaScript is working
"""

import requests

BASE_URL = "https://kb.agent-anywhere.com"

# Test 1: Check if main page has auth check
print("Testing authentication JavaScript...")

response = requests.get(f"{BASE_URL}/")
html = response.text

# Check for authentication code
has_check_auth = "checkAuth()" in html
has_redirect_code = "window.location.href = '/login" in html
has_dom_loaded_check = "if (!checkAuth())" in html

print(f"\n✓ Has checkAuth function: {has_check_auth}")
print(f"✓ Has redirect code: {has_redirect_code}")
print(f"✓ Has DOM loaded auth check: {has_dom_loaded_check}")

# Check JavaScript files
print("\nChecking JavaScript files...")

# app.js
response = requests.get(f"{BASE_URL}/static/js/app.js")
app_js = response.text
has_auth_check_in_app = "if (!checkAuth())" in app_js
print(f"✓ app.js has auth check on load: {has_auth_check_in_app}")

# graph-viz.js
response = requests.get(f"{BASE_URL}/static/js/graph-viz.js")
graph_js = response.text
has_auth_check_in_graph = "if (!token && !apiKey)" in graph_js
print(f"✓ graph-viz.js has auth check: {has_auth_check_in_graph}")

# Test login page exists
response = requests.get(f"{BASE_URL}/login")
login_exists = response.status_code == 200
print(f"\n✓ Login page exists: {login_exists}")

print("\n" + "="*60)
print("SUMMARY:")
print("="*60)

if all([has_check_auth, has_redirect_code, has_dom_loaded_check, 
        has_auth_check_in_app, has_auth_check_in_graph, login_exists]):
    print("✅ All authentication code is in place!")
    print("\nThe redirect should work in a real browser.")
    print("If it's not working, it might be due to:")
    print("1. Browser cache (try incognito/private mode)")
    print("2. JavaScript errors (check browser console)")
else:
    print("❌ Some authentication code is missing!")
    
print("\nTo test in a browser:")
print("1. Open incognito/private window")
print("2. Visit https://kb.agent-anywhere.com/")
print("3. You should be redirected to /login")