# genres/processors/google_processor.py
"""
Google Books API response processor.
"""

from typing import List, Dict


def process_google_response(raw_data: Dict) -> List[str]:
    """
    Extract genres from Google Books API response.
    
    Extracts from:
    - mainCategory field
    - categories array
    
    Args:
        raw_data: Raw JSON response from Google Books API
    
    Returns:
        List of extracted genres/categories
    """
    genres = set()
    
    items = raw_data.get("items", [])
    for item in items:
        volume_info = item.get("volumeInfo", {})
        
        # Extract mainCategory
        main_category = volume_info.get("mainCategory", "")
        if main_category and main_category.strip():
            genres.add(main_category.strip())
        
        # Extract from categories array
        categories = volume_info.get("categories", [])
        for category in categories:
            if category and category.strip():
                genres.add(category.strip())
    
    return list(genres)