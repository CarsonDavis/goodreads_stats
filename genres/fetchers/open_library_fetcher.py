# genres/fetchers/open_library_fetcher.py
"""
Open Library API data fetcher implementing Edition + Work strategy.
"""

from typing import Optional, Dict, Tuple
from ..models import BookInfo
from ..api_caller import APICaller


def fetch_open_library_data(book: BookInfo, api_caller: APICaller) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Fetch book data from Open Library using Edition + Work strategy.
    
    Strategy:
    1. Try ISBN lookup for Edition data (and extract Work ID)
    2. If Work ID found, fetch Work data
    3. If no ISBN, use search API to find Work ID, then fetch Work data
    
    Args:
        book: Book information
        api_caller: Configured API caller
    
    Returns:
        (edition_data, work_data) - Raw JSON responses, either can be None
    """
    edition_data = None
    work_data = None
    work_id = None
    
    # Step 1: Try ISBN lookup for Edition data
    if book.isbn13 or book.isbn:
        isbn = book.isbn13 or book.isbn
        edition_data, work_id = _fetch_edition_data(isbn, api_caller)
    
    # Step 2: If no work_id from Edition, try search API
    if not work_id:
        work_id = _search_for_work_id(book.title, book.author, api_caller)
    
    # Step 3: Fetch Work data if we have a work_id
    if work_id:
        work_data = _fetch_work_data(work_id, api_caller)
    
    return edition_data, work_data


def _fetch_edition_data(isbn: str, api_caller: APICaller) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Fetch Edition data and extract Work ID.
    
    Returns:
        (edition_data, work_id)
    """
    url = "https://openlibrary.org/api/books"
    params = {
        "bibkeys": f"ISBN:{isbn}",
        "format": "json",
        "jscmd": "data"
    }
    
    success, status_code, data = api_caller.get(url, params)
    
    if success and data:
        # Get the first (and usually only) book entry
        book_data = list(data.values())[0] if data else {}
        
        # Extract work_id from works array
        work_id = None
        works = book_data.get("works", [])
        if works and len(works) > 0:
            work_key = works[0].get("key", "")
            if work_key and work_key.startswith("/works/"):
                work_id = work_key.split("/")[-1]  # Extract ID from "/works/OL123W"
        
        return data, work_id
    
    return None, None


def _search_for_work_id(title: str, author: str, api_caller: APICaller) -> Optional[str]:
    """
    Search for Work ID using title and author.
    
    Returns:
        work_id if found, None otherwise
    """
    url = "https://openlibrary.org/search.json"
    params = {
        "title": title,
        "author": author,
        "limit": 5
    }
    
    success, status_code, data = api_caller.get(url, params)
    
    if success and data and data.get("numFound", 0) > 0:
        # Get the first result's work key
        first_doc = data["docs"][0]
        work_key = first_doc.get("key", "")
        if work_key and work_key.startswith("/works/"):
            return work_key.split("/")[-1]
    
    return None


def _fetch_work_data(work_id: str, api_caller: APICaller) -> Optional[Dict]:
    """
    Fetch Work data using work_id.
    
    Returns:
        work_data if successful, None otherwise
    """
    url = f"https://openlibrary.org/works/{work_id}.json"
    
    success, status_code, data = api_caller.get(url)
    
    if success and data:
        return data
    
    return None