# run_single_book.py
"""
Runs the book data enrichment pipeline for a single, specified book.
"""
import sys
import os
import logging

# Add the project root to the Python path to allow for correct module imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from genres.models import BookInfo
from genres.book_data_pipeline import BookDataOrchestrator

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def run_single_book_pipeline(book: BookInfo):
    """
    Initializes the orchestrator and runs the pipeline for one book.
    """
    print(f"🚀 STARTING SINGLE BOOK ENRICHMENT: {book.title} by {book.author}")
    print("=" * 70)

    # Initialize orchestrator
    orchestrator = BookDataOrchestrator(rate_limit=1.0)

    # The enrich_books method expects a list
    enriched_books = orchestrator.enrich_books([book])

    if not enriched_books:
        print("❌ Pipeline did not return an enriched book object.")
        return

    # Display detailed results for the single book
    orchestrator.display_detailed_book_analysis(book.title)

    print("\n" + "=" * 70)
    print("✅ SINGLE BOOK ENRICHMENT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    # Define the book to be processed
    # Example: One of the Expanse novellas like "The Churn" or "The Sins of Our Fathers"
    # You can change the details here to run a different book.
    book_to_process = BookInfo(
        title="The Churn",
        author="James S.A. Corey",
        isbn13=None, # Often not available for novellas
        isbn=None,
        goodreads_id="21530921"
    )

    # Run the pipeline for the specified book
    run_single_book_pipeline(book_to_process)