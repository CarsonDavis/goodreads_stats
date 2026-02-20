#!/usr/bin/env python3
"""
Example usage of the analytics models for dashboard data preparation.

Demonstrates loading Goodreads data for time-series analytics while
treating re-reads as single entries to avoid skewing statistics.
"""

import logging
from collections import defaultdict, Counter
from genres.analytics_csv_processor import AnalyticsCSVProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    print("📊 GOODREADS ANALYTICS DATA PREPARATION")
    print("=" * 60)

    # Load analytics data
    processor = AnalyticsCSVProcessor()

    try:
        # Load only read books (exclude to-read) with a sample for testing
        books = processor.load_books_for_analytics(
            "data/goodreads_library_export-2025.06.15.csv",
            include_unread=False,  # Only read books for time-series
            sample_size=100,  # Larger sample to get read books
        )

        # Generate summary report
        summary = processor.export_analytics_summary(books)
        print_summary_report(summary)

        # Demonstrate time-series analytics
        print_time_series_analysis(books)

        # Show rating analytics
        print_rating_analysis(books)

        # Show re-read handling
        print_reread_analysis(books)

        # Export sample data for dashboard
        export_dashboard_data(books[:10])  # Just first 10 for demo

    except FileNotFoundError:
        print("❌ CSV file not found. Place your Goodreads export at:")
        print("   data/goodreads_library_export-2025.06.15.csv")


def print_summary_report(summary: dict):
    """Print overall summary statistics"""
    print("\n📈 ANALYTICS SUMMARY")
    print("-" * 40)
    print(f"Total books: {summary['total_books']}")
    print(f"Read books: {summary['read_books']}")
    print(f"Rated books: {summary['rated_books']}")
    print(f"Books with read dates: {summary['books_with_dates']}")
    print(f"Books with page counts: {summary['books_with_pages']}")
    print(
        f"Books originally re-read: {summary['re_read_count']} (treated as single reads)"
    )
    print(f"Reading years: {summary['reading_years']}")
    print(f"Average rating: {summary['avg_rating']:.1f}")
    print(f"Total pages read: {summary['total_pages']:,}")
    print(f"Unique authors: {summary['unique_authors']}")


def print_time_series_analysis(books):
    """Demonstrate time-series analytics capabilities"""
    print("\n📅 TIME-SERIES ANALYSIS")
    print("-" * 40)

    # Books by year
    yearly_counts = defaultdict(int)
    yearly_pages = defaultdict(int)
    yearly_ratings = defaultdict(list)

    for book in books:
        if book.is_read and book.reading_year:
            yearly_counts[book.reading_year] += 1  # Always 1, never re-read count
            if book.num_pages:
                yearly_pages[book.reading_year] += book.num_pages
            if book.is_rated:
                yearly_ratings[book.reading_year].append(book.my_rating)

    print("Books read by year:")
    for year in sorted(yearly_counts.keys()):
        pages = yearly_pages[year]
        avg_rating = (
            sum(yearly_ratings[year]) / len(yearly_ratings[year])
            if yearly_ratings[year]
            else 0
        )
        print(
            f"  {year}: {yearly_counts[year]} books, {pages:,} pages, avg rating {avg_rating:.1f}"
        )


def print_rating_analysis(books):
    """Show rating distribution and trends"""
    print("\n⭐ RATING ANALYSIS")
    print("-" * 40)

    rated_books = [book for book in books if book.is_rated]
    if not rated_books:
        print("No rated books found")
        return

    # Rating distribution
    rating_counts = Counter(book.my_rating for book in rated_books)
    print("Rating distribution:")
    for rating in sorted(rating_counts.keys()):
        count = rating_counts[rating]
        percentage = (count / len(rated_books)) * 100
        stars = "⭐" * rating
        print(f"  {stars} ({rating}): {count} books ({percentage:.1f}%)")

    # Compare my rating vs average rating
    rating_diffs = []
    for book in rated_books:
        if book.average_rating:
            diff = book.my_rating - book.average_rating
            rating_diffs.append(diff)

    if rating_diffs:
        avg_diff = sum(rating_diffs) / len(rating_diffs)
        print(f"\nAverage difference from Goodreads rating: {avg_diff:+.2f}")
        if avg_diff > 0:
            print("  → You tend to rate books higher than average")
        elif avg_diff < 0:
            print("  → You tend to rate books lower than average")
        else:
            print("  → Your ratings align with Goodreads average")


def print_reread_analysis(books):
    """Show how re-reads are handled"""
    print("\n🔄 RE-READ HANDLING")
    print("-" * 40)

    rereads = [book for book in books if book.read_count_original > 1]

    print(f"Books originally read multiple times: {len(rereads)}")
    print("Treatment for analytics: Each book counted as 1 read using latest date")

    if rereads:
        print("\nExample re-read books:")
        for book in rereads[:3]:
            print(f'  📖 "{book.title}"')
            print(f"     Original read count: {book.read_count_original}")
            print(f"     Analytics read count: {book.read_count_for_analytics}")
            print(f"     Latest read date: {book.date_read}")


def export_dashboard_data(books):
    """Show dashboard export format"""
    print("\n📊 DASHBOARD DATA EXPORT SAMPLE")
    print("-" * 40)

    print("Sample books in dashboard format:")
    for book in books[:3]:
        dashboard_data = book.to_dashboard_dict()
        print(f"\n📖 {dashboard_data['title']}")
        print(f"   Reading date: {dashboard_data['date_read']}")
        print(f"   Reading year: {dashboard_data['reading_year']}")
        print(f"   My rating: {dashboard_data['my_rating']}")
        print(f"   Pages: {dashboard_data['num_pages']}")
        print(
            f"   Was re-read: {dashboard_data['was_reread']} (treated as single read)"
        )


if __name__ == "__main__":
    main()
