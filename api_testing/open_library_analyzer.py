# api/open_library_analyzer.py
"""
Enhanced Open Library analyzer implementing Edition + Work lookup strategy.
"""

import pandas as pd
import json
import re
import logging
import requests
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from collections import Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
    """Enhanced API response structure for Edition + Work analysis"""
    api_name: str
    book_info: BookInfo
    success: bool
    response_time: float
    edition_genres: List[str]  # From ISBN/Edition lookup
    work_genres: List[str]     # From Work lookup
    genres: List[str]          # Final merged list
    work_id: Optional[str] = None
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


class EnhancedOpenLibraryClient:
    """Enhanced Open Library client with Edition + Work lookup strategy"""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.base_url = "https://openlibrary.org/api/books"
        self.work_base_url = "https://openlibrary.org"

    def get_book_info(self, book: BookInfo) -> APIResponse:
        """Get book information using Edition + Work lookup strategy"""
        start_time = time.time()
        
        edition_genres = []
        work_genres = []
        work_id = None
        
        # Step 1: Try ISBN lookup for Edition data
        if book.isbn13 or book.isbn:
            isbn = book.isbn13 or book.isbn
            edition_genres, work_id = self._get_edition_data(isbn)
        
        # Step 2: If no work_id from ISBN, try search API
        if not work_id:
            work_id = self._search_for_work_id(book.title, book.author)
        
        # Step 3: Get Work data if we have a work_id
        if work_id:
            work_genres = self._get_work_data(work_id)
        
        # Step 4: Merge results
        all_genres = set(edition_genres + work_genres)
        final_genres = list(all_genres)
        
        response_time = time.time() - start_time
        success = len(final_genres) > 0 or len(edition_genres) > 0
        
        return APIResponse(
            api_name="OpenLibrary Enhanced",
            book_info=book,
            success=success,
            response_time=response_time,
            edition_genres=edition_genres,
            work_genres=work_genres,
            genres=final_genres,
            work_id=work_id,
            error_message=None if success else "No data found"
        )

    def _get_edition_data(self, isbn: str) -> tuple[List[str], Optional[str]]:
        """Get subjects and work_id from Edition (ISBN) lookup"""
        self.rate_limiter.wait()
        
        url = f"{self.base_url}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data:
                    book_data = list(data.values())[0]
                    
                    # Extract subjects from Edition
                    subjects = []
                    for subject in book_data.get("subjects", []):
                        if isinstance(subject, dict):
                            name = subject.get("name", "")
                        else:
                            name = str(subject)
                        if name:
                            subjects.append(name.strip())
                    
                    # Extract work_id
                    work_id = None
                    works = book_data.get("works", [])
                    if works and len(works) > 0:
                        work_key = works[0].get("key", "")
                        if work_key:
                            work_id = work_key.split("/")[-1]  # Extract ID from "/works/OL123W"
                    
                    return subjects, work_id
                    
        except Exception as e:
            self.logger.error(f"Edition lookup failed: {e}")
        
        return [], None

    def _search_for_work_id(self, title: str, author: str) -> Optional[str]:
        """Search for work_id using title and author"""
        self.rate_limiter.wait()
        
        search_url = "https://openlibrary.org/search.json"
        params = {"title": title, "author": author, "limit": 5}
        
        try:
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data.get("numFound", 0) > 0:
                    # Get the first result's work key
                    first_doc = data["docs"][0]
                    work_key = first_doc.get("key", "")
                    if work_key and work_key.startswith("/works/"):
                        return work_key.split("/")[-1]
                        
        except Exception as e:
            self.logger.error(f"Work search failed: {e}")
        
        return None

    def _get_work_data(self, work_id: str) -> List[str]:
        """Get subjects from Work lookup"""
        self.rate_limiter.wait()
        
        url = f"{self.work_base_url}/works/{work_id}.json"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                subjects = []
                for subject in data.get("subjects", []):
                    if subject and subject.strip():
                        subjects.append(subject.strip())
                
                return subjects
                
        except Exception as e:
            self.logger.error(f"Work lookup failed: {e}")
        
        return []


class BookAPITester:
    """Main testing orchestrator focused on Open Library analysis"""

    def __init__(self):
        self.client = EnhancedOpenLibraryClient()
        self.results = []
        self.test_books = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_goodreads_data(self, csv_path: str, sample_size: Optional[int] = None) -> List[BookInfo]:
        """Load and clean Goodreads export data"""
        df = pd.read_csv(csv_path)

        if sample_size:
            df = df.sample(n=min(sample_size, len(df)), random_state=42).reset_index(drop=True)

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

    def test_apis(self, books: List[BookInfo], max_books: int = 50) -> None:
        """Test Open Library with the provided books"""
        test_books = books[:max_books]

        self.logger.info(f"Testing Open Library with {len(test_books)} books...")

        for i, book in enumerate(test_books, 1):
            self.logger.info(f"Testing book {i}/{len(test_books)}: {book.title}")

            try:
                response = self.client.get_book_info(book)
                self.results.append(asdict(response))

                self.logger.info(
                    f"  Success: {response.success}, "
                    f"Time: {response.response_time:.2f}s, "
                    f"Edition: {len(response.edition_genres)}, "
                    f"Work: {len(response.work_genres)}, "
                    f"Total: {len(response.genres)}"
                )

            except Exception as e:
                self.logger.error(f"Error testing {book.title}: {e}")

    def display_coverage_report(self) -> None:
        """Display success rate and coverage analysis"""
        if not self.results:
            print("No results to analyze")
            return

        total = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        success_rate = (successful / total) * 100

        print("\n" + "=" * 60)
        print("📊 OPEN LIBRARY COVERAGE REPORT")
        print("=" * 60)
        print(f"Total books tested: {total}")
        print(f"Successfully found: {successful}")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Failed lookups: {total - successful}")

    def display_subject_depth_analysis(self) -> None:
        """Analyze the depth and quality of subject data"""
        if not self.results:
            return

        successful = [r for r in self.results if r["success"]]
        
        if not successful:
            print("\n❌ No successful results to analyze")
            return

        print("\n" + "=" * 60)
        print("📚 SUBJECT DEPTH ANALYSIS")
        print("=" * 60)

        # Calculate statistics
        total_subjects = [len(r["genres"]) for r in successful]
        edition_subjects = [len(r["edition_genres"]) for r in successful]
        work_subjects = [len(r["work_genres"]) for r in successful]

        print(f"Average subjects per book: {sum(total_subjects) / len(total_subjects):.1f}")
        print(f"  - From Edition lookup: {sum(edition_subjects) / len(edition_subjects):.1f}")
        print(f"  - From Work lookup: {sum(work_subjects) / len(work_subjects):.1f}")
        
        print(f"\nMaximum subjects found: {max(total_subjects)}")
        print(f"Minimum subjects found: {min(total_subjects)}")
        
        zero_subjects = sum(1 for count in total_subjects if count == 0)
        print(f"Books with 0 subjects: {zero_subjects} ({zero_subjects/len(successful)*100:.1f}%)")

        # Find most and least subject-rich books
        max_idx = total_subjects.index(max(total_subjects))
        min_idx = total_subjects.index(min(total_subjects))
        
        print(f"\nMost subjects: '{successful[max_idx]['book_info']['title']}' ({max(total_subjects)} subjects)")
        print(f"Fewest subjects: '{successful[min_idx]['book_info']['title']}' ({min(total_subjects)} subjects)")

    def display_edition_vs_work_comparison(self, book_title: str) -> None:
        """Compare Edition vs Work data for a specific book"""
        book_results = [r for r in self.results 
                       if book_title.lower() in r["book_info"]["title"].lower()]

        if not book_results:
            print(f"\n❌ Book '{book_title}' not found in results")
            return

        result = book_results[0]
        
        print(f"\n🔍 EDITION vs WORK COMPARISON: {result['book_info']['title']}")
        print("-" * 60)
        print(f"Work ID: {result.get('work_id', 'Not found')}")
        
        print(f"\n📖 Edition subjects ({len(result['edition_genres'])}):")
        for subject in result['edition_genres']:
            print(f"   • {subject}")
        
        print(f"\n📚 Work subjects ({len(result['work_genres'])}):")
        for subject in result['work_genres']:
            print(f"   • {subject}")
        
        print(f"\n🎯 Final merged subjects ({len(result['genres'])}):")
        for subject in result['genres']:
            print(f"   • {subject}")

        # Analysis
        edition_only = set(result['edition_genres']) - set(result['work_genres'])
        work_only = set(result['work_genres']) - set(result['edition_genres'])
        
        if edition_only:
            print(f"\n🔸 Edition-only subjects: {list(edition_only)}")
        if work_only:
            print(f"\n🔹 Work-only subjects: {list(work_only)}")

    def display_common_subjects_report(self) -> None:
        """Display most common subjects across the collection"""
        if not self.results:
            return

        successful = [r for r in self.results if r["success"]]
        
        if not successful:
            return

        all_subjects = []
        for result in successful:
            all_subjects.extend(result["genres"])

        subject_counts = Counter(all_subjects)
        
        print("\n" + "=" * 60)
        print("🏷️  TOP 25 MOST COMMON SUBJECTS")
        print("=" * 60)
        
        for subject, count in subject_counts.most_common(25):
            percentage = (count / len(successful)) * 100
            print(f"{count:3d} ({percentage:4.1f}%) • {subject}")

    def save_results(self, csv_file: str = "api/results/open_library_enhanced_results.csv", 
                    json_file: str = "api/results/open_library_enhanced_report.json") -> None:
        """Save detailed results"""
        import os
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        
        if self.results:
            df = pd.DataFrame(self.results)
            df.to_csv(csv_file, index=False)
            print(f"💾 Detailed results saved to '{csv_file}'")

        # Create summary report
        if self.results:
            successful = [r for r in self.results if r["success"]]
            total_subjects = [len(r["genres"]) for r in successful] if successful else [0]
            
            report = {
                "total_books": len(self.results),
                "successful_lookups": len(successful),
                "success_rate": len(successful) / len(self.results) * 100 if self.results else 0,
                "avg_subjects_per_book": sum(total_subjects) / len(total_subjects) if total_subjects else 0,
                "max_subjects": max(total_subjects) if total_subjects else 0,
                "min_subjects": min(total_subjects) if total_subjects else 0,
            }
            
            with open(json_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"📊 Summary report saved to '{json_file}'")


def main():
    """Main execution function"""
    print("🔍 ENHANCED OPEN LIBRARY ANALYZER")
    print("Edition + Work Lookup Strategy")
    print("=" * 60)
    
    # Initialize tester
    tester = BookAPITester()
    
    # Load Goodreads data
    csv_path = "data/goodreads_library_export-2025.06.15.csv"
    books = tester.load_goodreads_data(csv_path, sample_size=20)  # Start with 20 books
    
    # Test books
    tester.test_apis(books)
    
    # Display reports
    tester.display_coverage_report()
    tester.display_subject_depth_analysis()
    tester.display_common_subjects_report()
    
    # Show specific book comparisons
    if tester.results:
        sample_books = ["Consider the Fork", "Son", "Radium Girls"]
        for book_title in sample_books:
            tester.display_edition_vs_work_comparison(book_title)
    
    # Save results
    tester.save_results()


if __name__ == "__main__":
    main()