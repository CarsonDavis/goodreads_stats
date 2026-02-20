#!/usr/bin/env python3
"""
Find the latest generated JSON file and provide the dashboard URL.
"""

import os
import glob
import json
from pathlib import Path

def find_latest_json():
    """Find the most recent JSON file in dashboard_data/"""
    dashboard_dir = Path("dashboard_data")
    
    if not dashboard_dir.exists():
        return None
    
    # Find all JSON files
    json_files = list(dashboard_dir.glob("*.json"))
    
    if not json_files:
        return None
    
    # Get the most recent by modification time
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    return latest_file

def extract_uuid_from_filename(filepath):
    """Extract UUID from filename"""
    filename = filepath.stem  # Remove .json extension
    
    # If it's just a UUID, return it
    if len(filename) == 36 and filename.count('-') == 4:
        return filename
    
    # If it contains a UUID, try to extract it
    import re
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    match = re.search(uuid_pattern, filename, re.IGNORECASE)
    
    if match:
        return match.group(0)
    
    return None

def get_dashboard_urls(uuid):
    """Generate dashboard URLs for different formats"""
    base_local = "http://localhost:8000/dashboard"
    
    return {
        "query": f"{base_local}/?uuid={uuid}",
        "hash": f"{base_local}/#{uuid}",
        "recommended": f"{base_local}/?uuid={uuid}"
    }

def main():
    print("🔍 DASHBOARD URL GENERATOR")
    print("=" * 50)
    
    # Find latest JSON file
    latest_file = find_latest_json()
    
    if not latest_file:
        print("❌ No JSON files found in dashboard_data/")
        print("💡 Generate data first: python create_dashboard_json.py")
        return
    
    # Extract UUID
    uuid = extract_uuid_from_filename(latest_file)
    
    if not uuid:
        print(f"❌ Could not extract UUID from: {latest_file.name}")
        return
    
    # Get file info
    try:
        with open(latest_file) as f:
            data = json.load(f)
        
        book_count = len(data.get('books', []))
        export_time = data.get('metadata', {}).get('export_timestamp', 'Unknown')
        
    except Exception as e:
        book_count = "Unknown"
        export_time = "Unknown"
    
    print(f"📄 Latest file: {latest_file.name}")
    print(f"📚 Books: {book_count}")
    print(f"⏰ Created: {export_time}")
    print(f"🆔 UUID: {uuid}")
    print()
    
    # Generate URLs
    urls = get_dashboard_urls(uuid)
    
    print("🌐 DASHBOARD URLS:")
    print("-" * 30)
    print(f"🔗 Query format: {urls['query']}")
    print(f"# Hash format:  {urls['hash']}")
    print()
    
    print("🚀 QUICK START:")
    print("1. Start local server: python -m http.server 8000")
    print(f"2. Open: {urls['recommended']}")
    print()
    
    print("📋 COPY THIS URL:")
    print(f"   {urls['recommended']}")
    print()
    
    print("☁️  PRODUCTION S3 CONFIG:")
    print("Configure in dashboard.js:")
    print(f"window.S3_BASE_URL = 'https://your-bucket.s3.amazonaws.com';")
    print(f"Then use: https://your-domain.com/dashboard/?uuid={uuid}")

if __name__ == "__main__":
    main()