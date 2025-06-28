# api/tester.py
"""
Main API testing orchestrator for analyzing book APIs.
"""

import pandas as pd
import json
import re
import logging
from dataclasses import asdict
from typing import List, Dict, Optional, Any
from collections import Counter

from ..api.models import BookInfo, APIResponse
from ..api.clients import BookAPIClient, GoogleBooksClient, OpenLibraryClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class BookAPITester:
    """Main testing orchestrator for book APIs"""

    def __init__(self):
        self.clients = {}
        self.results = []
        self.test_books = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_client(self, name: str, client: BookAPIClient):
        """Add an API client for testing"""
        self.clients[name] = client

    def load_goodreads_data(
        self, csv_path: str, sample_size: Optional[int] = None
    ) -> List[BookInfo]:
        """Load and clean Goodreads export data"""
        df = pd.read_csv(csv_path)

        if sample_size:
            df = df.sample(n=min(sample_size, len(df)), random_state=42).reset_index(
                drop=True
            )

        books = []
        for _, row in df.iterrows():
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
        self.test_books = books
        return books

    def _clean_isbn(self, isbn_str: str) -> str:
        """Clean ISBN from Excel formatting"""
        if not isbn_str or pd.isna(isbn_str):
            return ""

        # Remove Excel formula formatting
        clean_isbn = re.sub(r'^="?([0-9X]+)"?$', r"\1", str(isbn_str))

        # Remove any non-alphanumeric characters except X
        clean_isbn = re.sub(r"[^0-9X]", "", clean_isbn.upper())

        # Validate length
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
                    for genre in genres[:10]:
                        print(f"      • {genre}")
                    if len(genres) > 10:
                        print(f"      ... and {len(genres) - 10} more")
                elif success:
                    print("    📝 No genres found")
                else:
                    error_msg = result.get("error_message", "Unknown error")
                    print(f"    ❌ Error: {error_msg}")

    def analyze_genre_patterns(self) -> None:
        """Analyze genre patterns across APIs"""
        if not self.results:
            print("No results to analyze")
            return

        print("\n" + "=" * 80)
        print("GENRE ANALYSIS BY API")
        print("=" * 80)

        api_genres = {}

        for result in self.results:
            api_name = result["api_name"]
            if result["success"] and result["genres"]:
                if api_name not in api_genres:
                    api_genres[api_name] = []
                api_genres[api_name].extend(result["genres"])

        for api_name, all_genres in api_genres.items():
            print(f"\n🔍 {api_name} Genre Analysis:")
            print(f"   Total genres collected: {len(all_genres)}")
            print(f"   Unique genres: {len(set(all_genres))}")

            # Most common genres
            genre_counts = Counter(all_genres)
            print(f"\n   📊 Most common genres:")
            for genre, count in genre_counts.most_common(10):
                print(f"      {count}x: {genre}")

            # Analyze genre complexity
            simple_genres = [
                g
                for g in set(all_genres)
                if "," not in g and "/" not in g and len(g.split()) <= 2
            ]
            complex_genres = [
                g for g in set(all_genres) if "," in g or "/" in g or len(g.split()) > 2
            ]

            print(f"\n   📝 Genre complexity:")
            print(
                f"      Simple genres: {len(simple_genres)} (e.g., {simple_genres[:3]})"
            )
            print(
                f"      Complex genres: {len(complex_genres)} (e.g., {complex_genres[:3]})"
            )

    def compare_apis_for_book(self, book_title: str) -> None:
        """Compare how different APIs categorize the same book"""
        print(f"\n🔍 API Comparison for: {book_title}")
        print("=" * 60)

        book_results = [
            r
            for r in self.results
            if book_title.lower() in r["book_info"]["title"].lower()
        ]

        if not book_results:
            print("❌ Book not found in results")
            return

        for result in book_results:
            api_name = result["api_name"]
            genres = result["genres"] if result["success"] else []

            print(f"\n{api_name}:")
            if genres:
                for genre in genres:
                    print(f"  • {genre}")
            else:
                print("  (No genres found)")

    def debug_api_responses(self, book_index: int = 0) -> None:
        """Debug API responses for a specific book"""
        if not self.test_books:
            print("❌ No test books available. Run load_goodreads_data first.")
            return

        if book_index >= len(self.test_books):
            print(
                f"❌ Book index {book_index} out of range. Available: 0-{len(self.test_books)-1}"
            )
            return

        book = self.test_books[book_index]
        print(f"\n🔍 DEBUGGING API RESPONSES FOR: {book.title} by {book.author}")
        print("=" * 80)

        # Debug Google Books
        for client_name, client in self.clients.items():
            if isinstance(client, GoogleBooksClient):
                client.debug_response(book)
                break

    def suggest_api_strategy(self) -> None:
        """Suggest the best API strategy based on results"""
        if not self.results:
            return

        report = self.generate_report()

        print("\n" + "=" * 80)
        print("🎯 RECOMMENDED API STRATEGY")
        print("=" * 80)

        for api_name, stats in report.items():
            print(f"\n{api_name}:")
            print(f"  ✓ Reliability: {stats['success_rate']:.0f}%")
            print(f"  ⚡ Speed: {stats['avg_response_time']:.2f}s average")
            print(
                f"  📚 Genre coverage: {stats['avg_genres_found']:.1f} genres per book"
            )

            if api_name == "Google Books":
                if stats["avg_genres_found"] < 2:
                    print(
                        "  ⚠️  Very limited genre data - use for basic categorization only"
                    )
                print("  💡 Best for: Quick, reliable basic categories")

            elif api_name == "OpenLibrary":
                if stats["avg_genres_found"] > 5:
                    print("  ✨ Rich subject data - excellent for detailed tagging")
                print("  💡 Best for: Detailed subject classification, academic use")

        # Overall recommendation
        print(f"\n🎯 OVERALL RECOMMENDATION:")
        best_detailed = max(report.items(), key=lambda x: x[1]["avg_genres_found"])
        best_reliable = max(report.items(), key=lambda x: x[1]["success_rate"])

        if (
            best_detailed[1]["avg_genres_found"]
            > best_reliable[1]["avg_genres_found"] * 3
        ):
            print(
                f"  Primary: Use {best_detailed[0]} for detailed genre classification"
            )
            print(
                f"  Fallback: Use {best_reliable[0]} for basic categories when detailed fails"
            )
        else:
            print(
                f"  Use {best_reliable[0]} as primary (best balance of reliability and detail)"
            )

        print(f"\n💡 For your book collection:")
        print(f"  • Start with the more detailed API for richer classification")
        print(f"  • Implement fallback to handle failures gracefully")
        print(f"  • Consider genre normalization/mapping for consistency")

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

    def save_results(
        self,
        csv_file: str = "api/results/api_test_results.csv",
        json_file: str = "api/results/api_performance_report.json",
    ) -> None:
        """Save results to files"""
        import os

        # Ensure the directory exists
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)
        os.makedirs(os.path.dirname(json_file), exist_ok=True)

        if self.results:
            df = pd.DataFrame(self.results)
            df.to_csv(csv_file, index=False)
            print(f"💾 Detailed results saved to '{csv_file}'")

        report = self.generate_report()
        if "error" not in report:
            with open(json_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"📊 Performance report saved to '{json_file}'")


def load_and_display_results(csv_file: str = "api/results/api_test_results.csv"):
    """Load existing results and display them"""
    try:
        import ast

        df = pd.read_csv(csv_file)

        # Convert string representations back to actual data types
        df["genres"] = df["genres"].apply(
            lambda x: ast.literal_eval(x) if pd.notna(x) and x != "[]" else []
        )
        df["book_info"] = df["book_info"].apply(
            lambda x: ast.literal_eval(x) if pd.notna(x) else {}
        )

        # Create temporary tester for display
        temp_tester = BookAPITester()
        temp_tester.results = df.to_dict("records")
        temp_tester.display_detailed_results()
        temp_tester.analyze_genre_patterns()
        temp_tester.suggest_api_strategy()

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
