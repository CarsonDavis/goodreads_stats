# genres/fetchers/google_fetcher.py
"""
Google Books API data fetcher.
"""

from typing import Optional, Dict
from ..models import BookInfo
from ..api_caller import APICaller


def fetch_google_data(book: BookInfo, api_caller: APICaller) -> Optional[Dict]:
    """
    Fetch book data from Google Books API.
    
    Query strategy:
    1. Try ISBN13 if available
    2. Try ISBN if available and different from ISBN13
    3. Fall back to title + author search
    
    Args:
        book: Book information
        api_caller: Configured API caller
    
    Returns:
        Raw JSON response from Google Books API, or None if all queries fail
    """
    base_url = "https://www.googleapis.com/books/v1/volumes"
    
    # Build query strategies in order of preference
    queries = []
    
    if book.isbn13:
        queries.append(f"isbn:{book.isbn13}")
    
    if book.isbn and book.isbn != book.isbn13:
        queries.append(f"isbn:{book.isbn}")
    
    # Title + author fallback
    title_author_query = f'intitle:"{book.title}" inauthor:"{book.author}"'
    queries.append(title_author_query)
    
    # Try each query until we get results
    for query in queries:
        params = {
            "q": query,
            "projection": "full",
            "maxResults": 5
        }
        
        success, status_code, data = api_caller.get(base_url, params)
        
        if success and data and data.get("totalItems", 0) > 0:
            return data
    
    # All queries failed
    return None