#!/usr/bin/env python3
# api/main.py
"""
Main script for testing book APIs with Goodreads export data.
"""

import os
import sys
from .tester import BookAPITester, load_and_display_results
from .clients import GoogleBooksClient, OpenLibraryClient


def main():
    """Main function to run API testing"""
    # Initialize the tester
    tester = BookAPITester()

    # Add API clients (adjust rate limits as needed)
    tester.add_client("google_books", GoogleBooksClient(rate_limit=1.0))
    tester.add_client("openlibrary", OpenLibraryClient(rate_limit=1.0))

    # Load Goodreads data
    csv_path = "data/goodreads_library_export-2025.06.15.csv"

    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        print("Please update the path to your Goodreads export file")
        return

    # Test with small sample first
    books = tester.load_goodreads_data(csv_path, sample_size=5)

    # Test APIs
    results_df = tester.test_apis(books, max_books_per_api=5)

    # Display results
    tester.display_detailed_results()
    tester.analyze_genre_patterns()
    tester.suggest_api_strategy()

    # Generate and print report
    report = tester.generate_report()
    print("\n=== API Performance Report ===")
    for api_name, stats in report.items():
        print(f"\n{api_name}:")
        print(f"  Success Rate: {stats['success_rate']:.1f}%")
        print(f"  Avg Response Time: {stats['avg_response_time']:.2f}s")
        print(f"  Avg Genres Found: {stats['avg_genres_found']:.1f}")
        print(
            f"  Books with Genres: {stats['books_with_genres']}/{stats['successful_requests']}"
        )

    # Save results
    tester.save_results()

    # Debug first book
    print("\n" + "=" * 80)
    print("🔍 DEBUGGING GOOGLE BOOKS API RESPONSE")
    print("=" * 80)
    tester.debug_api_responses(0)


def quick_debug():
    """Quick debug function for investigating specific issues"""
    tester = BookAPITester()
    tester.add_client("google_books", GoogleBooksClient(rate_limit=1.0))

    csv_path = "data/goodreads_library_export-2025.06.15.csv"
    books = tester.load_goodreads_data(csv_path, sample_size=1)

    if books:
        print("🔍 Quick Google Books API Debug")
        print("Comparing API data vs. what you see on Google Books website...")
        tester.debug_api_responses(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        quick_debug()
    elif len(sys.argv) > 1 and sys.argv[1] == "load":
        csv_file = (
            sys.argv[2] if len(sys.argv) > 2 else "api/results/api_test_results.csv"
        )
        load_and_display_results(csv_file)
    else:
        main()
