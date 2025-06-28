#!/usr/bin/env python3
"""
Example usage of the refactored Book Genre Enrichment Pipeline.

Demonstrates the clean separation of concerns:
1. CSVProcessor handles CSV loading
2. GenreEnricher handles single book enrichment  
3. BookFeeder orchestrates batch processing
"""

import logging
from genres import GenreEnricher, CSVProcessor, BookFeeder, BookInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def example_single_book():
    """Example: Enrich a single book directly"""
    print("\n" + "="*50)
    print("🔍 SINGLE BOOK ENRICHMENT EXAMPLE")
    print("="*50)
    
    # Create a single book
    book = BookInfo(
        title="The Great Gatsby",
        author="F. Scott Fitzgerald",
        isbn13="9780743273565",
        isbn=None,
        goodreads_id="4671"
    )
    
    # Initialize enricher
    enricher = GenreEnricher(rate_limit=0.5)
    
    # Enrich the book
    enriched_book = enricher.enrich_book(book)
    
    # Display results
    print(f"📚 Book: {enriched_book.input_info.title}")
    print(f"🔍 Google Genres: {enriched_book.processed_google_genres}")
    print(f"🔍 OpenLib Subjects: {enriched_book.processed_openlib_genres}")
    print(f"🎯 Final Genres: {enriched_book.final_genres}")
    print(f"📝 Processing Log:")
    for log_entry in enriched_book.processing_log:
        print(f"   • {log_entry}")


def example_csv_batch():
    """Example: Process books from CSV"""
    print("\n" + "="*50)
    print("📊 CSV BATCH PROCESSING EXAMPLE")
    print("="*50)
    
    # Load books from CSV
    csv_processor = CSVProcessor()
    books = csv_processor.load_books(
        "data/goodreads_library_export-2025.06.15.csv", 
        sample_size=3  # Small sample for demo
    )
    
    # Initialize enricher and feeder
    enricher = GenreEnricher(rate_limit=1.0)
    feeder = BookFeeder(enricher)
    
    # Process books
    enriched_books = feeder.process_books(books)
    
    # Display summary
    print(f"\n📊 BATCH PROCESSING SUMMARY")
    print(f"Total books processed: {len(enriched_books)}")
    
    for enriched_book in enriched_books:
        print(f"\n📚 {enriched_book.input_info.title}")
        print(f"   Final genres: {len(enriched_book.final_genres)}")
        print(f"   Status: {'✅ Success' if enriched_book.final_genres else '❌ No genres found'}")


def example_mixed_workflow():
    """Example: Combine CSV loading with individual book processing"""
    print("\n" + "="*50)
    print("🔄 MIXED WORKFLOW EXAMPLE") 
    print("="*50)
    
    # Load books from CSV
    csv_processor = CSVProcessor()
    books = csv_processor.load_books(
        "data/goodreads_library_export-2025.06.15.csv",
        sample_size=5
    )
    
    # Initialize enricher
    enricher = GenreEnricher(rate_limit=0.5)
    
    # Process first book individually
    print(f"Processing first book individually:")
    enriched_book = enricher.enrich_book(books[0])
    print(f"   {enriched_book.input_info.title}: {len(enriched_book.final_genres)} genres")
    
    # Process remaining books in batch
    if len(books) > 1:
        print(f"\nProcessing remaining {len(books)-1} books in batch:")
        feeder = BookFeeder(enricher)
        batch_enriched = feeder.process_books(books[1:])
        
        for book in batch_enriched:
            print(f"   {book.input_info.title}: {len(book.final_genres)} genres")


def main():
    """Run all examples"""
    print("🚀 BOOK GENRE ENRICHMENT PIPELINE - EXAMPLES")
    print("Demonstrating clean separation of concerns\n")
    
    # Example 1: Single book enrichment
    example_single_book()
    
    # Example 2: CSV batch processing  
    try:
        example_csv_batch()
    except FileNotFoundError:
        print("\n⚠️  CSV file not found - skipping batch example")
        print("   Place your Goodreads export at: data/goodreads_library_export-2025.06.15.csv")
    
    # Example 3: Mixed workflow
    try:
        example_mixed_workflow()
    except FileNotFoundError:
        print("\n⚠️  CSV file not found - skipping mixed workflow example")
    
    print(f"\n" + "="*50)
    print("✅ EXAMPLES COMPLETE")
    print("="*50)
    print("Key Architecture Benefits:")
    print("• Single book enrichment: GenreEnricher.enrich_book()")
    print("• CSV processing: CSVProcessor.load_books()")  
    print("• Batch orchestration: BookFeeder.process_books()")
    print("• Clean separation of concerns")
    print("• Ready for async/parallel enhancement")


if __name__ == "__main__":
    main()