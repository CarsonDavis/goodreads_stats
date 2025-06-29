#!/usr/bin/env python3
"""
SMART ADAPTIVE PIPELINE

Automatically detects environment and uses optimal strategy:
- Local: 15 concurrent threads (4-6 minutes, free)
- AWS Lambda: 1 Lambda per book (10-30 seconds, ~$0.05)

Same code, optimal performance everywhere!
"""

import asyncio
import logging
import time
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def main():
    # Detect environment
    is_lambda = (
        os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None or
        os.environ.get('AWS_EXECUTION_ENV', '').startswith('AWS_Lambda')
    )
    
    if is_lambda:
        print("☁️  RUNNING IN AWS LAMBDA")
        print("Strategy: 1 Lambda function per book")
        print("Expected: 10-30 seconds, ~$0.05 cost")
    else:
        print("💻 RUNNING LOCALLY") 
        print("Strategy: 15 concurrent async threads")
        print("Expected: 4-6 minutes, free")
    
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        from genres import AnalyticsCSVProcessor, EnvironmentAwareBookPipeline, create_dashboard_json
        
        # Step 1: Load books
        print("📊 Loading books from CSV...")
        csv_processor = AnalyticsCSVProcessor()
        books = csv_processor.load_books_for_analytics(
            "data/goodreads_library_export-2025.06.15.csv",
            include_unread=False,
            sample_size=None  # All books
        )
        
        # Convert to BookInfo for enrichment
        from genres import BookInfo
        book_infos = []
        for book in books:
            book_info = BookInfo(
                title=book.title,
                author=book.author,
                isbn13=book.isbn13,
                isbn=book.isbn,
                goodreads_id=book.goodreads_id
            )
            book_infos.append(book_info)
        
        print(f"📚 Processing {len(book_infos)} books...")
        
        # Step 2: Smart enrichment
        pipeline = EnvironmentAwareBookPipeline(max_local_concurrent=15)
        enriched_data = await pipeline.process_books_smart(book_infos)
        
        # Step 3: Transfer back to BookAnalytics and export
        enhanced_books = []
        for original_book, enriched_item in zip(books, enriched_data):
            # Transfer enriched data back
            original_book.final_genres = enriched_item.final_genres
            original_book.genre_enrichment_success = len(enriched_item.final_genres) > 0
            original_book.thumbnail_url = enriched_item.thumbnail_url
            original_book.small_thumbnail_url = enriched_item.small_thumbnail_url
            enhanced_books.append(original_book)
        
        # Step 4: Create dashboard JSON
        json_path = create_dashboard_json(enhanced_books)
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("🎉 SMART PIPELINE COMPLETE!")
        print("=" * 60)
        
        if is_lambda:
            print(f"☁️  AWS Lambda execution: {elapsed:.1f} seconds")
            print(f"💰 Estimated cost: ~$0.05")
        else:
            print(f"💻 Local execution: {elapsed/60:.1f} minutes ({elapsed:.1f} seconds)")
            print(f"💰 Cost: Free")
        
        print(f"📄 Dashboard JSON: {json_path}")
        print()
        print("🌐 Get dashboard URL:")
        print("python get_dashboard_url.py")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Pipeline failed after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    # Check for required packages
    try:
        import aiohttp
    except ImportError:
        print("⚠️  Installing aiohttp...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    
    exit(asyncio.run(main()))