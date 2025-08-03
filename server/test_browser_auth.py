#!/usr/bin/env python3
"""
Test authentication in a browser-like environment using Selenium
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Test configuration
BASE_URL = "https://kb.agent-anywhere.com"
API_KEY = "gGiC5I-xoEXuM1AXpPvaV1H82AFTGfadDjLiUq2D1fc"

def test_browser_auth():
    """Test authentication flow in a real browser"""
    
    # Setup Chrome in headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        # This will fail if Chrome/ChromeDriver not installed
        # But will show what the test would do
        driver = webdriver.Chrome(options=chrome_options)
        
        print("Testing browser authentication flow...")
        
        # Clear localStorage
        driver.get(BASE_URL)
        driver.execute_script("localStorage.clear();")
        
        # Test 1: Visit homepage without auth
        print("\n1. Testing redirect without auth...")
        driver.get(BASE_URL)
        time.sleep(2)  # Wait for JavaScript to execute
        
        current_url = driver.current_url
        print(f"   Current URL: {current_url}")
        
        if "/login" in current_url:
            print("   ✓ Redirected to login page")
        else:
            print("   ✗ Not redirected to login page")
            
        # Test 2: Login with API key
        print("\n2. Testing API key login...")
        driver.get(f"{BASE_URL}/login")
        
        # Click "Use API Key" button
        api_key_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "apiKeyToggle"))
        )
        api_key_btn.click()
        
        # Enter API key
        api_key_input = driver.find_element(By.ID, "apiKey")
        api_key_input.send_keys(API_KEY)
        
        # Submit
        login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        login_btn.click()
        
        time.sleep(2)
        
        # Check if redirected to main page
        if driver.current_url == BASE_URL or driver.current_url == f"{BASE_URL}/":
            print("   ✓ Successfully logged in and redirected")
        else:
            print(f"   ✗ Login failed, still at: {driver.current_url}")
            
        # Test 3: Check if stats load
        print("\n3. Testing stats display...")
        entity_count = driver.find_element(By.ID, "entity-count").text
        episode_count = driver.find_element(By.ID, "episode-count").text
        relation_count = driver.find_element(By.ID, "relation-count").text
        
        print(f"   Entities: {entity_count}")
        print(f"   Episodes: {episode_count}")
        print(f"   Relations: {relation_count}")
        
        if entity_count != "0" or episode_count != "0" or relation_count != "0":
            print("   ✓ Stats loaded successfully")
        else:
            print("   ✗ Stats not loading")
            
        driver.quit()
        
    except Exception as e:
        print(f"Browser test failed: {e}")
        print("\nTo run browser tests, you need:")
        print("1. Chrome/Chromium browser")
        print("2. ChromeDriver")
        print("3. pip install selenium")

def test_with_curl():
    """Simpler test using curl to check JavaScript execution"""
    import subprocess
    
    print("\nTesting with curl simulation...")
    
    # Test 1: Check if main page loads
    result = subprocess.run(
        ["curl", "-s", BASE_URL],
        capture_output=True,
        text=True
    )
    
    html_content = result.stdout
    
    # Check for auth check in JavaScript
    if "checkAuth()" in html_content and "DOMContentLoaded" in html_content:
        print("✓ Authentication check is in the page")
    else:
        print("✗ Authentication check missing from page")
        
    # Check if login page exists
    result = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{BASE_URL}/login"],
        capture_output=True,
        text=True
    )
    
    if result.stdout.strip() == "200":
        print("✓ Login page exists")
    else:
        print(f"✗ Login page returns: {result.stdout.strip()}")
        
    # Test with API key
    result = subprocess.run(
        ["curl", "-s", "-H", f"X-API-Key: {API_KEY}", f"{BASE_URL}/stats"],
        capture_output=True,
        text=True
    )
    
    if "entity_count" in result.stdout:
        print("✓ API key authentication works")
    else:
        print("✗ API key authentication failed")

if __name__ == "__main__":
    print("=" * 60)
    print("Browser-like Authentication Test")
    print(f"Target: {BASE_URL}")
    print("=" * 60)
    
    # Try browser test first
    try:
        test_browser_auth()
    except:
        print("\nBrowser test not available, using curl simulation...")
        test_with_curl()