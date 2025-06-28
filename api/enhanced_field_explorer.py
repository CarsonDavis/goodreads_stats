# api/enhanced_field_explorer.py
"""
Enhanced Google Books API explorer testing different parameter combinations.
"""

import requests
import json
import sys


def get_book_data(query: str, **params) -> dict:
    """Get raw Google Books API response with custom parameters"""
    url = "https://www.googleapis.com/books/v1/volumes"
    
    # Default parameters
    default_params = {
        "q": query,
        "maxResults": 5,
        "projection": "full"
    }
    
    # Override with custom parameters
    default_params.update(params)
    
    print(f"🔍 API Request: {url}")
    print(f"📋 Parameters: {default_params}")
    
    response = requests.get(url, params=default_params)
    print(f"📡 Response Status: {response.status_code}")
    print(f"🔗 Actual URL: {response.url}")
    
    return response.json()


def print_nested_dict(d, indent=0, max_depth=3):
    """Print dictionary with nested structure (limited depth)"""
    if indent > max_depth:
        print("  " * indent + "... (truncated)")
        return
        
    for key, value in d.items():
        if isinstance(value, dict):
            print("  " * indent + f"{key}:")
            print_nested_dict(value, indent + 1, max_depth)
        elif isinstance(value, list):
            print("  " * indent + f"{key}: [list with {len(value)} items]")
            if value and len(value) <= 3:
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        print("  " * (indent + 1) + f"[{i}]:")
                        print_nested_dict(item, indent + 2, max_depth)
                    else:
                        print("  " * (indent + 1) + f"[{i}]: {item}")
        else:
            # Truncate long strings
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print("  " * indent + f"{key}: {value}")


def test_different_search_methods(isbn: str, title: str):
    """Test different ways to search for the same book"""
    
    print("🧪 TESTING DIFFERENT SEARCH METHODS")
    print("=" * 80)
    
    search_methods = [
        ("ISBN Only", f"isbn:{isbn}"),
        ("Title Only", f'intitle:"{title}"'),
        ("Subject Search", f"subject:cooking"),
        ("Title + Subject", f'intitle:"{title}" subject:cooking'),
        ("Exact ISBN", isbn),
        ("Plain Title", title),
    ]
    
    for method_name, query in search_methods:
        print(f"\n📖 {method_name}: {query}")
        print("-" * 60)
        
        data = get_book_data(query, maxResults=3)
        
        if "items" not in data:
            print("❌ No results found")
            continue
        
        for i, book in enumerate(data["items"]):
            volume_info = book.get("volumeInfo", {})
            title_found = volume_info.get("title", "Unknown")
            categories = volume_info.get("categories", [])
            main_category = volume_info.get("mainCategory", "None")
            
            print(f"   📚 Result {i+1}: {title_found}")
            print(f"      🎯 mainCategory: {main_category}")
            print(f"      📂 categories: {categories}")


def test_parameter_combinations(query: str):
    """Test different parameter combinations"""
    
    print("\n🔧 TESTING PARAMETER COMBINATIONS")
    print("=" * 80)
    
    param_sets = [
        {"projection": "lite"},
        {"projection": "full"},
        {"projection": "full", "printType": "books"},
        {"projection": "full", "filter": "partial"},
        {"projection": "full", "orderBy": "relevance"},
        {"projection": "full", "langRestrict": "en"},
    ]
    
    for i, params in enumerate(param_sets):
        print(f"\n🧪 Test {i+1}: {params}")
        print("-" * 40)
        
        data = get_book_data(query, **params)
        
        if "items" not in data:
            print("❌ No results found")
            continue
            
        book = data["items"][0]
        volume_info = book.get("volumeInfo", {})
        
        # Focus on category-related fields
        categories = volume_info.get("categories", [])
        main_category = volume_info.get("mainCategory", "None")
        subjects = volume_info.get("subjects", [])  # Check if this exists
        
        print(f"📚 Title: {volume_info.get('title', 'Unknown')}")
        print(f"🎯 mainCategory: {main_category}")
        print(f"📂 categories: {categories}")
        print(f"📖 subjects: {subjects}")
        
        # Check for any field containing "subject" or "category"
        subject_fields = {}
        for key, value in volume_info.items():
            if "subject" in key.lower() or "category" in key.lower() or "genre" in key.lower():
                subject_fields[key] = value
        
        if subject_fields:
            print(f"🔍 Other subject/category fields: {subject_fields}")


def main():
    if len(sys.argv) < 2:
        # Use the Consider the Fork book
        isbn = "9780465056972"
        title = "Consider the Fork"
        print(f"Using default book: {title} (ISBN: {isbn})")
    else:
        query = " ".join(sys.argv[1:])
        if query.isdigit() or (len(query) in [10, 13] and query.replace("-", "").isdigit()):
            isbn = query
            title = "Unknown"
        else:
            isbn = "9780465056972"  # fallback
            title = query
    
    print(f"📚 Enhanced Google Books Analysis")
    print(f"🔍 ISBN: {isbn}")
    print(f"📖 Title: {title}")
    print("=" * 80)
    
    # Test different search methods
    test_different_search_methods(isbn, title)
    
    # Test parameter combinations
    test_parameter_combinations(f"isbn:{isbn}")
    
    # Get full detailed view of one result
    print("\n📋 FULL DETAILED VIEW (isbn search)")
    print("=" * 80)
    data = get_book_data(f"isbn:{isbn}")
    if data.get("items"):
        print_nested_dict(data["items"][0])


if __name__ == "__main__":
    main()