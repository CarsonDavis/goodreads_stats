# api/book_data_pipeline.py
"""
Main orchestrator for the Book Data Enrichment Pipeline.
"""

import pandas as pd
import json
import re
import logging
from typing import List, Optional
from collections import Counter

from .enriched_models import EnrichedBook
from .models import BookInfo
from .api_caller import APICaller
from .fetchers import fetch_google_data, fetch_open_library_data
from .processors import process_google_response, process_open_library_response
from .genre_merger import merge_and_normalize, analyze_genre_overlap

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class BookDataOrchestrator:
    """
    Main orchestrator that coordinates the book data enrichment pipeline.
    """

    def __init__(self, rate_limit: float = 1.0):
        self.api_caller = APICaller(rate_limit=rate_limit)
        self.enriched_books: List[EnrichedBook] = []
        self.logger = logging.getLogger(self.__class__.__name__)

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

        self.logger.info(f"Loaded {len(books)} books for enrichment")
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

    def enrich_books(
        self, books: List[BookInfo], max_books: Optional[int] = None
    ) -> List[EnrichedBook]:
        """
        Main pipeline method - enriches each book through the full pipeline.
        """
        books_to_process = books[:max_books] if max_books else books
        self.enriched_books = []

        self.logger.info(
            f"Starting enrichment pipeline for {len(books_to_process)} books"
        )

        for i, book in enumerate(books_to_process, 1):
            self.logger.info(
                f"Processing book {i}/{len(books_to_process)}: {book.title}"
            )

            # Initialize enriched book
            enriched_book = EnrichedBook(input_info=book)
            enriched_book.add_log(f"Starting enrichment pipeline")

            # Step 1: Fetch raw data
            self._fetch_data(enriched_book)

            # Step 2: Process raw data into genres
            self._process_data(enriched_book)

            # Step 3: Merge and normalize final genres
            self._merge_and_finalize(enriched_book)

            # Store enriched book
            self.enriched_books.append(enriched_book)

            self.logger.info(
                f"  Complete: Google={len(enriched_book.processed_google_genres)}, "
                f"OpenLib={len(enriched_book.processed_openlib_genres)}, "
                f"Final={len(enriched_book.final_genres)}"
            )

        return self.enriched_books

    def _fetch_data(self, enriched_book: EnrichedBook) -> None:
        """Fetch raw data from both APIs"""
        book = enriched_book.input_info

        # Fetch Google Books data
        try:
            google_data = fetch_google_data(book, self.api_caller)
            if google_data:
                enriched_book.google_response = google_data
                enriched_book.add_log("Google Books: Success")
            else:
                enriched_book.add_log("Google Books: No data found")
        except Exception as e:
            enriched_book.add_log(f"Google Books: Error - {str(e)}")

        # Fetch Open Library data
        try:
            edition_data, work_data = fetch_open_library_data(book, self.api_caller)
            if edition_data:
                enriched_book.openlib_edition_response = edition_data
                enriched_book.add_log("Open Library Edition: Success")
            if work_data:
                enriched_book.openlib_work_response = work_data
                enriched_book.add_log("Open Library Work: Success")
            if not edition_data and not work_data:
                enriched_book.add_log("Open Library: No data found")
        except Exception as e:
            enriched_book.add_log(f"Open Library: Error - {str(e)}")

    def _process_data(self, enriched_book: EnrichedBook) -> None:
        """Process raw API responses into genre lists"""

        # Process Google Books data
        if enriched_book.google_response:
            try:
                google_genres = process_google_response(enriched_book.google_response)
                enriched_book.processed_google_genres = google_genres
                enriched_book.add_log(
                    f"Google Books: Extracted {len(google_genres)} genres"
                )
            except Exception as e:
                enriched_book.add_log(f"Google Books processing error: {str(e)}")

        # Process Open Library data
        if (
            enriched_book.openlib_edition_response
            or enriched_book.openlib_work_response
        ):
            try:
                openlib_genres = process_open_library_response(
                    enriched_book.openlib_edition_response,
                    enriched_book.openlib_work_response,
                )
                enriched_book.processed_openlib_genres = openlib_genres
                enriched_book.add_log(
                    f"Open Library: Extracted {len(openlib_genres)} subjects"
                )
            except Exception as e:
                enriched_book.add_log(f"Open Library processing error: {str(e)}")

    def _merge_and_finalize(self, enriched_book: EnrichedBook) -> None:
        """Merge and normalize final genre list"""
        try:
            final_genres = merge_and_normalize(
                enriched_book.processed_google_genres,
                enriched_book.processed_openlib_genres,
            )
            enriched_book.final_genres = final_genres
            enriched_book.add_log(
                f"Final: {len(final_genres)} merged and normalized genres"
            )
        except Exception as e:
            enriched_book.add_log(f"Genre merging error: {str(e)}")

    # Reporting methods
    def display_pipeline_summary(self) -> None:
        """Display overall pipeline performance summary"""
        if not self.enriched_books:
            print("No books processed yet")
            return

        total = len(self.enriched_books)
        google_success = sum(1 for book in self.enriched_books if book.google_response)
        openlib_success = sum(
            1
            for book in self.enriched_books
            if book.openlib_edition_response or book.openlib_work_response
        )
        final_success = sum(
            1 for book in self.enriched_books if len(book.final_genres) > 0
        )

        print("\n" + "=" * 70)
        print("📊 BOOK DATA ENRICHMENT PIPELINE SUMMARY")
        print("=" * 70)
        print(f"Total books processed: {total}")
        print(
            f"Google Books success: {google_success} ({google_success/total*100:.1f}%)"
        )
        print(
            f"Open Library success: {openlib_success} ({openlib_success/total*100:.1f}%)"
        )
        print(
            f"Final enrichment success: {final_success} ({final_success/total*100:.1f}%)"
        )

        # Genre statistics
        total_genres = [len(book.final_genres) for book in self.enriched_books]
        if total_genres:
            print(f"\nGenre Statistics:")
            print(
                f"  Average genres per book: {sum(total_genres)/len(total_genres):.1f}"
            )
            print(f"  Maximum genres: {max(total_genres)}")
            print(f"  Books with 0 genres: {sum(1 for x in total_genres if x == 0)}")

    def display_source_comparison(self) -> None:
        """Compare Google Books vs Open Library performance"""
        if not self.enriched_books:
            return

        google_counts = [
            len(book.processed_google_genres) for book in self.enriched_books
        ]
        openlib_counts = [
            len(book.processed_openlib_genres) for book in self.enriched_books
        ]

        print("\n" + "=" * 70)
        print("🔍 SOURCE COMPARISON: Google Books vs Open Library")
        print("=" * 70)
        print(f"Google Books:")
        print(f"  Average genres per book: {sum(google_counts)/len(google_counts):.1f}")
        print(f"  Books with data: {sum(1 for x in google_counts if x > 0)}")

        print(f"\nOpen Library:")
        print(
            f"  Average subjects per book: {sum(openlib_counts)/len(openlib_counts):.1f}"
        )
        print(f"  Books with data: {sum(1 for x in openlib_counts if x > 0)}")

        # Overlap analysis for books that have both
        overlaps = []
        for book in self.enriched_books:
            if book.processed_google_genres and book.processed_openlib_genres:
                overlap = analyze_genre_overlap(
                    book.processed_google_genres, book.processed_openlib_genres
                )
                overlaps.append(overlap)

        if overlaps:
            avg_overlap = sum(o["overlap_percentage"] for o in overlaps) / len(overlaps)
            print(f"\nGenre Overlap (for books with both sources):")
            print(f"  Books with both sources: {len(overlaps)}")
            print(f"  Average overlap percentage: {avg_overlap:.1f}%")

    def display_detailed_book_analysis(self, book_title: str) -> None:
        """Display detailed analysis for a specific book"""
        matching_books = [
            book
            for book in self.enriched_books
            if book_title.lower() in book.input_info.title.lower()
        ]

        if not matching_books:
            print(f"\n❌ Book '{book_title}' not found in processed books")
            return

        book = matching_books[0]

        print(f"\n📚 DETAILED ANALYSIS: {book.input_info.title}")
        print(f"Author: {book.input_info.author}")
        print("=" * 70)

        print(f"\n🔍 Google Books ({len(book.processed_google_genres)} genres):")
        for genre in book.processed_google_genres:
            print(f"   • {genre}")

        print(f"\n🔍 Open Library ({len(book.processed_openlib_genres)} subjects):")
        for genre in book.processed_openlib_genres:
            print(f"   • {genre}")

        print(f"\n🎯 Final Merged ({len(book.final_genres)} genres):")
        for genre in book.final_genres:
            print(f"   • {genre}")

        # Show overlap analysis
        if book.processed_google_genres and book.processed_openlib_genres:
            overlap = analyze_genre_overlap(
                book.processed_google_genres, book.processed_openlib_genres
            )
            print(f"\n📊 Overlap Analysis:")
            print(f"   Common: {overlap['overlapping']}")
            print(f"   Google only: {overlap['google_only']}")
            print(f"   OpenLib only: {overlap['openlib_only']}")

        print(f"\n📝 Processing Log:")
        for log_entry in book.processing_log:
            print(f"   • {log_entry}")

    def display_top_genres(self, top_n: int = 25) -> None:
        """Display most common genres across all books"""
        if not self.enriched_books:
            return

        all_genres = []
        for book in self.enriched_books:
            all_genres.extend(book.final_genres)

        genre_counts = Counter(all_genres)

        print(f"\n🏷️  TOP {top_n} GENRES ACROSS ALL BOOKS")
        print("=" * 70)

        for genre, count in genre_counts.most_common(top_n):
            percentage = (count / len(self.enriched_books)) * 100
            print(f"{count:3d} ({percentage:4.1f}%) • {genre}")

    def save_results(
        self,
        csv_file: str = "api/results/enriched_books.csv",
        json_file: str = "api/results/enrichment_report.json",
    ) -> None:
        """Save enriched results"""
        import os

        # Ensure directories exist
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)
        os.makedirs(os.path.dirname(json_file), exist_ok=True)

        if self.enriched_books:
            # Create summary data for CSV
            summary_data = []
            for book in self.enriched_books:
                summary = book.get_summary()
                summary_data.append(summary)

            df = pd.DataFrame(summary_data)
            df.to_csv(csv_file, index=False)
            print(f"💾 Enriched results saved to '{csv_file}'")

            # Create detailed report
            report = {
                "total_books": len(self.enriched_books),
                "pipeline_stats": {
                    "google_success_rate": sum(
                        1 for b in self.enriched_books if b.google_response
                    )
                    / len(self.enriched_books)
                    * 100,
                    "openlib_success_rate": sum(
                        1
                        for b in self.enriched_books
                        if b.openlib_edition_response or b.openlib_work_response
                    )
                    / len(self.enriched_books)
                    * 100,
                    "final_success_rate": sum(
                        1 for b in self.enriched_books if len(b.final_genres) > 0
                    )
                    / len(self.enriched_books)
                    * 100,
                },
                "genre_stats": {
                    "avg_final_genres": sum(
                        len(b.final_genres) for b in self.enriched_books
                    )
                    / len(self.enriched_books),
                    "avg_google_genres": sum(
                        len(b.processed_google_genres) for b in self.enriched_books
                    )
                    / len(self.enriched_books),
                    "avg_openlib_genres": sum(
                        len(b.processed_openlib_genres) for b in self.enriched_books
                    )
                    / len(self.enriched_books),
                },
            }

            with open(json_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"📊 Pipeline report saved to '{json_file}'")


def main():
    """Main execution function"""
    print("🚀 BOOK DATA ENRICHMENT PIPELINE")
    print("Combining Google Books + Open Library for Maximum Coverage")
    print("=" * 70)

    # Initialize orchestrator
    orchestrator = BookDataOrchestrator(rate_limit=1.0)

    # Load data
    csv_path = "data/goodreads_library_export-2025.06.15.csv"
    books = orchestrator.load_goodreads_data(csv_path, sample_size=10)  # Start small

    # Run enrichment pipeline
    enriched_books = orchestrator.enrich_books(books)

    # Display results
    orchestrator.display_pipeline_summary()
    orchestrator.display_source_comparison()
    orchestrator.display_top_genres()

    # Show detailed analysis for a few books
    sample_titles = ["Consider the Fork", "Son", "Radium Girls"]
    for title in sample_titles:
        orchestrator.display_detailed_book_analysis(title)

    # Save results
    orchestrator.save_results()


if __name__ == "__main__":
    main()
