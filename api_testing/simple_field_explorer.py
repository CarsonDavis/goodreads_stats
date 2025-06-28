# api/simple_field_explorer.py
"""
Simple tool to see all Google Books API fields for one book.
"""

import requests
import json
import sys


def get_book_data(query: str) -> dict:
    """Get raw Google Books API response"""
    url = "https://www.googleapis.com/books/v1/volumes"
    
    # If query looks like ISBN, use isbn: prefix
    if query.replace("-", "").replace(" ", "").isdigit() and len(query.replace("-", "").replace(" ", "")) in [10, 13]:
        formatted_query = f"isbn:{query}"
    else:
        formatted_query = query
    
    params = {
        "q": formatted_query,
        "maxResults": 1,
        "projection": "full"
    }
    
    print(f"🔍 Searching for: {formatted_query}")
    
    response = requests.get(url, params=params)
    return response.json()


def print_nested_dict(d, indent=0):
    """Print dictionary with nested structure"""
    for key, value in d.items():
        if isinstance(value, dict):
            print("  " * indent + f"{key}:")
            print_nested_dict(value, indent + 1)
        elif isinstance(value, list):
            print("  " * indent + f"{key}: [list with {len(value)} items]")
            if value and len(value) <= 3:  # Show first few items if small list
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        print("  " * (indent + 1) + f"[{i}]:")
                        print_nested_dict(item, indent + 2)
                    else:
                        print("  " * (indent + 1) + f"[{i}]: {item}")
        else:
            # Truncate long strings
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print("  " * indent + f"{key}: {value}")


def main():
    if len(sys.argv) < 2:
        query = "The Hobbit"
        print(f"No query provided, using default: '{query}'")
    else:
        query = " ".join(sys.argv[1:])
    
    print(f"📚 Getting Google Books data for: {query}")
    print("=" * 60)
    
    data = get_book_data(query)
    
    if "items" not in data:
        print("❌ No books found")
        print("Response:", data)
        return
    
    book = data["items"][0]
    
    print("🔍 ALL AVAILABLE FIELDS:")
    print_nested_dict(book)


if __name__ == "__main__":
    main()