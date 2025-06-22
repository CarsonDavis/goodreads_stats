import pandas as pd
import requests
import time
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import logging
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class BookInfo:
    """Standardized book information structure"""

    title: str
    author: str
    isbn13: Optional[str] = None
    isbn: Optional[str] = None
    goodreads_id: Optional[str] = None


@dataclass
class APIResponse:
    """Standardized API response structure"""

    api_name: str
    book_info: BookInfo
    success: bool
    response_time: float
    genres: List[str]
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None


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
        # Try ISBN13 first, then ISBN, then title+author
        search_queries = []

        if book.isbn13:
            search_queries.append(f"isbn:{book.isbn13}")
        if book.isbn and book.isbn != book.isbn13:
            search_queries.append(f"isbn:{book.isbn}")

        # Fallback to title+author search
        title_author_query = f'intitle:"{book.title}" inauthor:"{book.author}"'
        search_queries.append(title_author_query)

        for query in search_queries:
            params = {"q": query}
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
            categories = volume_info.get("categories", [])

            for category in categories:
                # Split on common delimiters and clean up
                sub_categories = re.split(r"[/,&]", category)
                for sub_cat in sub_categories:
                    clean_cat = sub_cat.strip()
                    if clean_cat:
                        genres.add(clean_cat)

        return list(genres)


class OpenLibraryClient(BookAPIClient):
    """OpenLibrary API client"""

    def __init__(self, rate_limit: float = 1.0):
        super().__init__(rate_limit)
        self.base_url = "https://openlibrary.org/api/books"

    def get_book_info(self, book: BookInfo) -> APIResponse:
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


class BookAPITester:
    """Main testing orchestrator"""

    def __init__(self):
        self.clients = {}
        self.results = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_client(self, name: str, client: BookAPIClient):
        """Add an API client for testing"""
        self.clients[name] = client

    def load_goodreads_data(
        self, csv_path: str, sample_size: Optional[int] = None
    ) -> List[BookInfo]:
        """Load and clean Goodreads export data"""
        df = pd.read_csv(csv_path)

        # Sample data if specified
        if sample_size:
            df = df.sample(n=min(sample_size, len(df))).reset_index(drop=True)

        books = []
        for _, row in df.iterrows():
            # Clean ISBN fields (remove Excel formatting)
            isbn13 = self._clean_isbn(row.get("ISBN13", ""))
            isbn = self._clean_isbn(row.get("ISBN", ""))

            book = BookInfo(
                title=str(row["Title"]),
                author=str(row["Author"]),
                isbn13=isbn13 if isbn13 else None,
                isbn=isbn if isbn else None,
                goodreads_id=str(row["Book Id"]),
            )
            books.append(book)

        self.logger.info(f"Loaded {len(books)} books for testing")
        return books

    def _clean_isbn(self, isbn_str: str) -> str:
        """Clean ISBN from Excel formatting like ='9780306825569'"""
        if not isbn_str or pd.isna(isbn_str):
            return ""

        # Remove Excel formula formatting
        clean_isbn = re.sub(r'^="?([0-9X]+)"?$', r"\1", str(isbn_str))

        # Remove any non-alphanumeric characters except X
        clean_isbn = re.sub(r"[^0-9X]", "", clean_isbn.upper())

        # Validate length (10 for ISBN, 13 for ISBN13)
        if len(clean_isbn) in [10, 13]:
            return clean_isbn

        return ""

    def test_apis(
        self, books: List[BookInfo], max_books_per_api: int = 10
    ) -> pd.DataFrame:
        """Test all registered APIs with the provided books"""

        test_books = books[:max_books_per_api]

        for api_name, client in self.clients.items():
            self.logger.info(f"Testing {api_name} with {len(test_books)} books...")

            for i, book in enumerate(test_books, 1):
                self.logger.info(
                    f"  {api_name}: Testing book {i}/{len(test_books)}: {book.title}"
                )

                try:
                    response = client.get_book_info(book)
                    self.results.append(asdict(response))

                    self.logger.info(
                        f"    Success: {response.success}, "
                        f"Time: {response.response_time:.2f}s, "
                        f"Genres: {len(response.genres)}"
                    )

                except Exception as e:
                    self.logger.error(f"    Error testing {book.title}: {e}")

                    error_response = APIResponse(
                        api_name=api_name,
                        book_info=book,
                        success=False,
                        response_time=0.0,
                        genres=[],
                        error_message=str(e),
                    )
                    self.results.append(asdict(error_response))

        return pd.DataFrame(self.results)

    def display_detailed_results(self) -> None:
        """Display detailed results in human-readable format"""
        if not self.results:
            print("No results to display")
            return

        print("\n" + "=" * 80)
        print("DETAILED RESULTS BY BOOK")
        print("=" * 80)

        # Group results by book
        books_tested = {}
        for result in self.results:
            book_info = result["book_info"]
            book_key = f"{book_info['title']} by {book_info['author']}"

            if book_key not in books_tested:
                books_tested[book_key] = []
            books_tested[book_key].append(result)

        for book_title, api_results in books_tested.items():
            print(f"\n📚 {book_title}")
            print("-" * len(book_title))

            for result in api_results:
                api_name = result["api_name"]
                success = result["success"]
                response_time = result["response_time"]
                genres = result["genres"]

                status = "✅ SUCCESS" if success else "❌ FAILED"
                print(f"\n  {api_name}: {status} ({response_time:.2f}s)")

                if success and genres:
                    print(f"    📝 Genres found ({len(genres)}):")
                    for genre in genres[:10]:  # Show first 10 genres
                        print(f"      • {genre}")
                    if len(genres) > 10:
                        print(f"      ... and {len(genres) - 10} more")
                elif success:
                    print("    📝 No genres found")
                else:
                    error_msg = result.get("error_message", "Unknown error")
                    print(f"    ❌ Error: {error_msg}")

        print("\n" + "=" * 80)

    def generate_report(self) -> Dict[str, Any]:
        """Generate summary report of API performance"""
        if not self.results:
            return {"error": "No results to analyze"}

        df = pd.DataFrame(self.results)

        report = {}

        for api_name in df["api_name"].unique():
            api_data = df[df["api_name"] == api_name]

            successful = api_data[api_data["success"] == True]

            report[api_name] = {
                "total_requests": len(api_data),
                "successful_requests": len(successful),
                "success_rate": len(successful) / len(api_data) * 100,
                "avg_response_time": api_data["response_time"].mean(),
                "min_response_time": api_data["response_time"].min(),
                "max_response_time": api_data["response_time"].max(),
                "avg_genres_found": (
                    successful["genres"].apply(len).mean() if len(successful) > 0 else 0
                ),
                "books_with_genres": (
                    len(successful[successful["genres"].apply(len) > 0])
                    if len(successful) > 0
                    else 0
                ),
            }

        return report


# Example usage
if __name__ == "__main__":
    # Initialize the tester
    tester = BookAPITester()

    # Add API clients (adjust rate limits as needed)
    tester.add_client(
        "google_books", GoogleBooksClient(rate_limit=1.0)
    )  # 1 request per second
    tester.add_client(
        "openlibrary", OpenLibraryClient(rate_limit=1.0)
    )  # 1 request per second

    # Load your Goodreads data (test with small sample first)
    books = tester.load_goodreads_data(
        "../data/goodreads_library_export-2025.06.15.csv", sample_size=5
    )

    # Test APIs
    results_df = tester.test_apis(books, max_books_per_api=5)

    # Display detailed results
    tester.display_detailed_results()

    # Generate report
    report = tester.generate_report()

    # Print results
    print("\n=== API Performance Report ===")
    for api_name, stats in report.items():
        print(f"\n{api_name}:")
        print(f"  Success Rate: {stats['success_rate']:.1f}%")
        print(f"  Avg Response Time: {stats['avg_response_time']:.2f}s")
        print(f"  Avg Genres Found: {stats['avg_genres_found']:.1f}")
        print(
            f"  Books with Genres: {stats['books_with_genres']}/{stats['successful_requests']}"
        )

    # Save detailed results
    results_df.to_csv("api_test_results.csv", index=False)

    with open("api_performance_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n💾 Detailed results saved to 'api_test_results.csv'")
    print(f"📊 Performance report saved to 'api_performance_report.json'")

    # Uncomment this line to display existing results instead of running new tests:
    # load_and_display_results("api_test_results.csv")


# Example usage for loading and displaying existing results
def load_and_display_results(csv_file: str = "api_test_results.csv"):
    """Load existing results and display them nicely"""
    try:
        df = pd.read_csv(csv_file)

        # Convert string representation of lists back to actual lists
        import ast

        df["genres"] = df["genres"].apply(
            lambda x: ast.literal_eval(x) if pd.notna(x) and x != "[]" else []
        )
        df["book_info"] = df["book_info"].apply(
            lambda x: ast.literal_eval(x) if pd.notna(x) else {}
        )

        # Create a temporary tester just for display
        temp_tester = BookAPITester()
        temp_tester.results = df.to_dict("records")
        temp_tester.display_detailed_results()

        # Generate and display report
        report = temp_tester.generate_report()
        print("\n=== API Performance Report ===")
        for api_name, stats in report.items():
            print(f"\n{api_name}:")
            print(f"  Success Rate: {stats['success_rate']:.1f}%")
            print(f"  Avg Response Time: {stats['avg_response_time']:.2f}s")
            print(f"  Avg Genres Found: {stats['avg_genres_found']:.1f}")
            print(
                f"  Books with Genres: {stats['books_with_genres']}/{stats['successful_requests']}"
            )

    except FileNotFoundError:
        print(f"❌ Results file '{csv_file}' not found. Run the test first!")
    except Exception as e:
        print(f"❌ Error loading results: {e}")
