# api/single_book_tester.py
"""
Single book testing tool for direct API comparison.
"""

import pandas as pd
import sys
import re
from typing import Optional

from .models import BookInfo
from .clients import GoogleBooksClient, OpenLibraryClient


class SingleBookTester:
    """Test APIs against a single book for detailed comparison"""

    def __init__(self):
        self.google_client = GoogleBooksClient(rate_limit=1.0)
        self.openlibrary_client = OpenLibraryClient(rate_limit=1.0)

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

    def load_book_by_title(self, csv_path: str, search_title: str) -> Optional[BookInfo]:
        """Load a specific book from CSV by searching title"""
        df = pd.read_csv(csv_path)
        
        # Search for book (case insensitive)
        matches = df[df['Title'].str.contains(search_title, case=False, na=False)]
        
        if matches.empty:
            print(f"❌ No books found matching '{search_title}'")
            print("Available books (first 10):")
            for i, title in enumerate(df['Title'].head(10)):
                print(f"  {i+1}. {title}")
            return None
        
        if len(matches) > 1:
            print(f"🔍 Found {len(matches)} books matching '{search_title}':")
            for i, (_, row) in enumerate(matches.iterrows()):
                print(f"  {i+1}. '{row['Title']}' by {row['Author']}")
            
            choice = input(f"\nEnter number (1-{len(matches)}) or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                return None
            
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(matches):
                    selected_row = matches.iloc[choice_idx]
                else:
                    print("Invalid choice")
                    return None
            except ValueError:
                print("Invalid choice")
                return None
        else:
            selected_row = matches.iloc[0]
            print(f"📚 Found: '{selected_row['Title']}' by {selected_row['Author']}")

        # Create BookInfo object
        isbn13 = self._clean_isbn(selected_row.get("ISBN13", ""))
        isbn = self._clean_isbn(selected_row.get("ISBN", ""))

        return BookInfo(
            title=str(selected_row["Title"]),
            author=str(selected_row["Author"]),
            isbn13=isbn13 if isbn13 else None,
            isbn=isbn if isbn else None,
            goodreads_id=str(selected_row["Book Id"]),
        )

    def test_book_detailed(self, book: BookInfo) -> None:
        """Test both APIs against a single book with detailed output"""
        print(f"\n{'='*80}")
        print(f"🔍 DETAILED API TESTING FOR: {book.title}")
        print(f"Author: {book.author}")
        print(f"ISBN: {book.isbn or 'N/A'}")
        print(f"ISBN13: {book.isbn13 or 'N/A'}")
        print(f"Goodreads ID: {book.goodreads_id}")
        print(f"{'='*80}")

        # Test Google Books
        print(f"\n📗 GOOGLE BOOKS API")
        print("-" * 40)
        
        gb_response = self.google_client.get_book_info(book)
        
        if gb_response.success:
            print(f"✅ SUCCESS ({gb_response.response_time:.2f}s)")
            
            # Show raw API data first
            if gb_response.raw_response and gb_response.raw_response.get("items"):
                item = gb_response.raw_response["items"][0]
                volume_info = item.get("volumeInfo", {})
                print(f"\n📊 Raw API Data:")
                print(f"   🎯 mainCategory: {volume_info.get('mainCategory', 'Not provided')}")
                print(f"   📂 categories: {volume_info.get('categories', 'Not provided')}")
                print(f"   🏢 Publisher: {volume_info.get('publisher', 'Not provided')}")
                print(f"   📖 Page Count: {volume_info.get('pageCount', 'Not provided')}")
            
            print(f"\n📝 Extracted genres ({len(gb_response.genres)}):")
            if gb_response.genres:
                for genre in gb_response.genres:
                    print(f"   • {genre}")
            else:
                print(f"   (No genres extracted)")
        else:
            print(f"❌ FAILED ({gb_response.response_time:.2f}s)")
            print(f"Error: {gb_response.error_message}")

        # Test OpenLibrary
        print(f"\n📘 OPENLIBRARY API")
        print("-" * 40)
        
        ol_response = self.openlibrary_client.get_book_info(book)
        
        if ol_response.success:
            print(f"✅ SUCCESS ({ol_response.response_time:.2f}s)")
            
            # Show raw API data if available
            if ol_response.raw_response:
                print(f"\n📊 Raw API Data:")
                print(f"   📚 Response type: {type(ol_response.raw_response)}")
                if isinstance(ol_response.raw_response, dict):
                    print(f"   🔢 Keys: {list(ol_response.raw_response.keys())}")
            
            print(f"\n📝 Extracted subjects ({len(ol_response.genres)}):")
            if ol_response.genres:
                for genre in ol_response.genres[:20]:  # Show first 20
                    print(f"   • {genre}")
                if len(ol_response.genres) > 20:
                    print(f"   ... and {len(ol_response.genres) - 20} more")
            else:
                print(f"   (No subjects extracted)")
        else:
            print(f"❌ FAILED ({ol_response.response_time:.2f}s)")
            print(f"Error: {ol_response.error_message}")

        # Compare results
        print(f"\n📊 COMPARISON SUMMARY")
        print("-" * 40)
        print(f"Google Books: {'✅' if gb_response.success else '❌'} | "
              f"{len(gb_response.genres)} genres | {gb_response.response_time:.2f}s")
        print(f"OpenLibrary:  {'✅' if ol_response.success else '❌'} | "
              f"{len(ol_response.genres)} subjects | {ol_response.response_time:.2f}s")

        if gb_response.success and ol_response.success:
            # Find common genres
            gb_genres_lower = {g.lower() for g in gb_response.genres}
            ol_genres_lower = {g.lower() for g in ol_response.genres}
            common = gb_genres_lower.intersection(ol_genres_lower)
            
            if common:
                print(f"\n🤝 Common classifications ({len(common)}):")
                for genre in sorted(common):
                    print(f"   • {genre}")

        print(f"\n💡 RECOMMENDATIONS:")
        if ol_response.success and len(ol_response.genres) > len(gb_response.genres) * 2:
            print("   • Use OpenLibrary for rich subject classification")
            print("   • OpenLibrary provides more detailed categorization")
        elif gb_response.success and not ol_response.success:
            print("   • Use Google Books as primary (more reliable for this book)")
        elif ol_response.success and not gb_response.success:
            print("   • Use OpenLibrary as primary (only working API for this book)")
        else:
            print("   • Both APIs provide useful but different perspectives")
            print("   • Consider combining results for comprehensive classification")

    def debug_google_books(self, book: BookInfo) -> None:
        """Debug Google Books API responses in detail"""
        print(f"\n🔍 GOOGLE BOOKS DEBUG for: {book.title}")
        print("="*60)
        self.google_client.debug_response(book)


def main():
    """Main function for single book testing"""
    if len(sys.argv) < 2:
        print("Usage: python -m api.single_book_tester <search_title>")
        print("Example: python -m api.single_book_tester 'Dune'")
        return

    search_title = " ".join(sys.argv[1:])
    csv_path = "data/goodreads_library_export-2025.06.15.csv"

    tester = SingleBookTester()
    
    # Load the book
    book = tester.load_book_by_title(csv_path, search_title)
    if not book:
        return

    # Test the book
    tester.test_book_detailed(book)
    
    # Ask if user wants debug info
    debug_choice = input("\n🔍 Want to see Google Books debug info? (y/n): ").strip().lower()
    if debug_choice == 'y':
        tester.debug_google_books(book)


if __name__ == "__main__":
    main()