# api_testing/clients.py
"""
API client classes for book information retrieval.
"""

import requests
import time
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from .models import BookInfo, APIResponse


class RateLimiter:
    """Simple rate limiter"""

    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0

    def wait(self):
        elapsed = time.time() - self.last_called
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_called = time.time()


class BookAPIClient(ABC):
    """Abstract base class for book API clients"""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_book_info(self, book: BookInfo) -> APIResponse:
        """Get book information from the API"""
        pass

    def _make_request(self, url: str, params: Dict = None) -> tuple[bool, float, Dict]:
        """Make HTTP request with timing"""
        self.rate_limiter.wait()
        start_time = time.time()

        try:
            response = requests.get(url, params=params, timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                return True, response_time, response.json()
            else:
                self.logger.warning(f"HTTP {response.status_code} for URL: {url}")
                return False, response_time, {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error(f"Request failed: {e}")
            return False, response_time, {"error": str(e)}


class GoogleBooksClient(BookAPIClient):
    """Google Books API client"""

    def __init__(self, api_key: Optional[str] = None, rate_limit: float = 1.0):
        super().__init__(rate_limit)
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/books/v1/volumes"

    def get_book_info(self, book: BookInfo) -> APIResponse:
        """Get book information from Google Books API"""
        search_queries = []

        if book.isbn13:
            search_queries.append(f"isbn:{book.isbn13}")
        if book.isbn and book.isbn != book.isbn13:
            search_queries.append(f"isbn:{book.isbn}")

        # Fallback to title+author search
        title_author_query = f'intitle:"{book.title}" inauthor:"{book.author}"'
        search_queries.append(title_author_query)

        response_time = 0.0  # Initialize for error handling

        for query in search_queries:
            # ALWAYS use projection=full to get mainCategory and all other fields
            params = {
                "q": query,
                "projection": "full",
                "maxResults": 5,  # Get more results to find better matches
            }
            if self.api_key:
                params["key"] = self.api_key

            success, response_time, data = self._make_request(self.base_url, params)

            if success and data.get("totalItems", 0) > 0:
                genres = self._extract_genres(data)
                return APIResponse(
                    api_name="Google Books",
                    book_info=book,
                    success=True,
                    response_time=response_time,
                    genres=genres,
                    raw_response=data,
                )

        # No successful results
        return APIResponse(
            api_name="Google Books",
            book_info=book,
            success=False,
            response_time=response_time,
            genres=[],
            error_message="No results found",
        )

    def _extract_genres(self, data: Dict) -> List[str]:
        """Extract genres/categories from Google Books response"""
        genres = set()

        for item in data.get("items", []):
            volume_info = item.get("volumeInfo", {})

            # Extract mainCategory
            main_category = volume_info.get("mainCategory", "")
            if main_category:
                genres.add(main_category.strip())

            # Extract from categories array
            categories = volume_info.get("categories", [])
            for category in categories:
                if category and category.strip():
                    genres.add(category.strip())

        return list(genres)

    def debug_response(self, book: BookInfo) -> None:
        """Debug what Google Books API returns for a specific book"""
        search_queries = []

        if book.isbn13:
            search_queries.append(f"isbn:{book.isbn13}")
        if book.isbn != book.isbn13:
            search_queries.append(f"isbn:{book.isbn}")

        title_author_query = f'intitle:"{book.title}" inauthor:"{book.author}"'
        search_queries.append(title_author_query)

        print(f"\n🔍 DEBUG: Google Books API Response for '{book.title}'")
        print("=" * 60)

        for i, query in enumerate(search_queries):
            print(f"\n📝 Query {i+1}: {query}")

            # Test both lite and full projections to compare
            param_sets = [
                {"q": query, "projection": "lite"},
                {"q": query, "projection": "full"},
                {"q": query, "projection": "full", "maxResults": 5},
            ]

            found_data = False
            for j, params in enumerate(param_sets):
                if self.api_key:
                    params["key"] = self.api_key

                success, response_time, data = self._make_request(self.base_url, params)

                if success and data.get("totalItems", 0) > 0:
                    print(f"\n   ✅ Parameter set {j+1}: {params}")

                    item = data.get("items", [{}])[0]
                    volume_info = item.get("volumeInfo", {})

                    print(f"   📚 Total Items Found: {data.get('totalItems', 0)}")
                    print(
                        f"   🎯 **mainCategory**: {volume_info.get('mainCategory', 'MISSING!')}"
                    )
                    print(f"   📂 categories: {volume_info.get('categories', 'None')}")
                    print(
                        f"   📖 MaturityRating: {volume_info.get('maturityRating', 'None')}"
                    )
                    print(f"   🏢 Publisher: {volume_info.get('publisher', 'None')}")

                    description = volume_info.get("description", "")
                    if description:
                        print(f"   📝 Description preview: {description[:150]}...")

                    extracted_genres = self._extract_genres(data)
                    print(
                        f"   🎭 Extracted genres ({len(extracted_genres)}): {extracted_genres}"
                    )

                    found_data = True
                    # DON'T return here - continue to test other parameter sets
                else:
                    print(f"   ❌ Parameter set {j+1} failed: {params}")

            if found_data:
                return  # Only return after testing all parameter sets for this query

        print(f"❌ No Google Books data found for '{book.title}'")


class OpenLibraryClient(BookAPIClient):
    """OpenLibrary API client"""

    def __init__(self, rate_limit: float = 1.0):
        super().__init__(rate_limit)
        self.base_url = "https://openlibrary.org/api/books"

    def get_book_info(self, book: BookInfo) -> APIResponse:
        """Get book information from OpenLibrary API"""
        # Try ISBN lookup first
        if book.isbn13 or book.isbn:
            isbn = book.isbn13 or book.isbn
            url = f"{self.base_url}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

            success, response_time, data = self._make_request(url)

            if success and data:
                genres = self._extract_genres(data)
                return APIResponse(
                    api_name="OpenLibrary",
                    book_info=book,
                    success=True,
                    response_time=response_time,
                    genres=genres,
                    raw_response=data,
                )

        # Fallback to search API
        search_url = "https://openlibrary.org/search.json"
        params = {"title": book.title, "author": book.author, "limit": 5}

        success, response_time, data = self._make_request(search_url, params)

        if success and data.get("numFound", 0) > 0:
            genres = self._extract_genres_from_search(data)
            return APIResponse(
                api_name="OpenLibrary",
                book_info=book,
                success=True,
                response_time=response_time,
                genres=genres,
                raw_response=data,
            )

        return APIResponse(
            api_name="OpenLibrary",
            book_info=book,
            success=False,
            response_time=response_time,
            genres=[],
            error_message="No results found",
        )

    def _extract_genres(self, data: Dict) -> List[str]:
        """Extract subjects from OpenLibrary book data"""
        genres = set()

        for book_data in data.values():
            subjects = book_data.get("subjects", [])
            for subject in subjects:
                if isinstance(subject, dict):
                    name = subject.get("name", "")
                else:
                    name = str(subject)

                if name:
                    genres.add(name.strip())

        return list(genres)

    def _extract_genres_from_search(self, data: Dict) -> List[str]:
        """Extract subjects from OpenLibrary search results"""
        genres = set()

        for doc in data.get("docs", []):
            subjects = doc.get("subject", [])
            for subject in subjects:
                if subject:
                    genres.add(subject.strip())

        return list(genres)