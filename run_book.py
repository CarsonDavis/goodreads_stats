#!/usr/bin/env python3
"""
Single book enrichment test using The Sins of Our Fathers (The Expanse, #9.5).

This demonstrates the clean architecture with a single Expanse novella,
showing how the GenreEnricher works independently of CSV processing.
"""

import logging
from genres import GenreEnricher, BookInfo

# Configure logging to see the enrichment process
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    print("🚀 SINGLE BOOK ENRICHMENT TEST")
    print("=" * 50)
    
    # Create BookInfo for "The Sins of Our Fathers" (Expanse #9.5)
    # This is a novella, perfect for testing the enrichment pipeline
    book = BookInfo(
        title="The Sins of Our Fathers (The Expanse, #9.5)",
        author="James S.A. Corey",
        isbn13="9780316669078",
        isbn=None,
        goodreads_id="59548471"
    )
    
    print(f"📚 Testing book: {book.title}")
    print(f"👤 Author: {book.author}")
    print(f"📖 ISBN13: {book.isbn13}")
    print(f"🆔 Goodreads ID: {book.goodreads_id}")
    print()
    
    # Initialize enricher with moderate rate limiting
    enricher = GenreEnricher(rate_limit=1.0)
    
    print("🔄 Starting enrichment process...")
    print("-" * 50)
    
    # Enrich the book
    enriched_book = enricher.enrich_book(book)
    
    print("-" * 50)
    print("✅ ENRICHMENT COMPLETE")
    print("=" * 50)
    
    # Display results
    print(f"📊 RESULTS FOR: {enriched_book.input_info.title}")
    print()
    
    print(f"🔍 Google Books Genres ({len(enriched_book.processed_google_genres)}):")
    if enriched_book.processed_google_genres:
        for genre in enriched_book.processed_google_genres:
            print(f"   • {genre}")
    else:
        print("   (none found)")
    print()
    
    print(f"🔍 Open Library Subjects ({len(enriched_book.processed_openlib_genres)}):")
    if enriched_book.processed_openlib_genres:
        for genre in enriched_book.processed_openlib_genres:
            print(f"   • {genre}")
    else:
        print("   (none found)")
    print()
    
    print(f"🎯 Final Merged Genres ({len(enriched_book.final_genres)}):")
    if enriched_book.final_genres:
        for genre in enriched_book.final_genres:
            print(f"   • {genre}")
    else:
        print("   (none found)")
    print()
    
    print("📝 Processing Log:")
    for log_entry in enriched_book.processing_log:
        print(f"   • {log_entry}")
    print()
    
    # Show raw API responses (truncated for readability)
    if enriched_book.google_response:
        print("📡 Google Books API Response: ✅ Success")
    else:
        print("📡 Google Books API Response: ❌ No data")
        
    if enriched_book.openlib_edition_response or enriched_book.openlib_work_response:
        print("📡 Open Library API Response: ✅ Success")
    else:
        print("📡 Open Library API Response: ❌ No data")
    
    print()
    print("=" * 50)
    print("🎉 SINGLE BOOK TEST COMPLETE")
    print("=" * 50)
    print("This demonstrates the clean architecture:")
    print("• GenreEnricher handles single book enrichment")
    print("• No CSV processing needed")
    print("• Ready for async/parallel enhancement")
    print("• Clear separation of concerns")

if __name__ == "__main__":
    main()