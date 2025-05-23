#!/usr/bin/env python3
"""
Test script to verify Flask app components work correctly
"""

import os
import sys
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

def test_flask_imports():
    """Test that all Flask app imports work"""
    try:
        from app_flask import app
        print("✅ Flask app imports successful")
        return True
    except ImportError as e:
        print(f"❌ Flask app import failed: {e}")
        return False

def test_selenium_setup():
    """Test that Selenium Chrome setup works"""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get("https://www.google.com")
        driver.quit()
        print("✅ Selenium Chrome setup successful")
        return True
    except Exception as e:
        print(f"❌ Selenium setup failed: {e}")
        return False

def test_template_exists():
    """Test that HTML template exists"""
    template_path = os.path.join("templates", "index.html")
    if os.path.exists(template_path):
        print("✅ HTML template exists")
        return True
    else:
        print("❌ HTML template missing")
        return False

def test_required_files():
    """Test that all required files exist"""
    required_files = [
        "app_flask.py",
        "requirements.txt", 
        "Procfile",
        "runtime.txt",
        "templates/index.html"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            all_exist = False
    
    return all_exist

def main():
    print("🧪 Testing Flask Google Maps Scraper Components\n")
    
    tests = [
        ("Required Files", test_required_files),
        ("Flask Imports", test_flask_imports),
        ("Template", test_template_exists),
        ("Selenium Setup", test_selenium_setup)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        if test_func():
            passed += 1
    
    print(f"\n🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your app is ready for deployment.")
    else:
        print("⚠️  Some tests failed. Please fix the issues before deploying.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
