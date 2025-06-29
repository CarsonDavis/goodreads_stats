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
        print("Expected: 10-30 seconds, ~$0.0003 cost per book")
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
        
        # Step 2: Smart enrichment with detailed timing
        print("🚀 Starting genre enrichment...")
        enrichment_start = time.time()
        
        pipeline = EnvironmentAwareBookPipeline(max_local_concurrent=15)
        enriched_data = await pipeline.process_books_smart(book_infos)
        
        enrichment_elapsed = time.time() - enrichment_start
        
        # Step 3: Transfer back to BookAnalytics and export
        print("📊 Merging enriched data...")
        merge_start = time.time()
        
        enhanced_books = []
        for original_book, enriched_item in zip(books, enriched_data):
            # Transfer enriched data back
            original_book.final_genres = enriched_item.final_genres
            original_book.genre_enrichment_success = len(enriched_item.final_genres) > 0
            original_book.thumbnail_url = enriched_item.thumbnail_url
            original_book.small_thumbnail_url = enriched_item.small_thumbnail_url
            enhanced_books.append(original_book)
        
        merge_elapsed = time.time() - merge_start
        
        # Step 4: Create dashboard JSON
        print("📄 Generating dashboard JSON...")
        export_start = time.time()
        json_path = create_dashboard_json(enhanced_books)
        export_elapsed = time.time() - export_start
        
        total_elapsed = time.time() - start_time
        
        # Calculate detailed statistics
        avg_time_per_book = enrichment_elapsed / len(book_infos) if book_infos else 0
        
        print("\n" + "=" * 60)
        print("🎉 SMART PIPELINE COMPLETE!")
        print("=" * 60)
        
        # Detailed timing breakdown
        print(f"📚 Processed {len(book_infos)} books")
        print(f"⏱️  Total time: {total_elapsed:.1f} seconds ({total_elapsed/60:.1f} minutes)")
        print(f"   • CSV loading: {enrichment_start - start_time:.1f}s")
        print(f"   • Genre enrichment: {enrichment_elapsed:.1f}s ({enrichment_elapsed/60:.1f} min)")
        print(f"   • Data merging: {merge_elapsed:.1f}s")
        print(f"   • JSON export: {export_elapsed:.1f}s")
        print(f"📈 Average per book: {avg_time_per_book:.2f} seconds")
        
        # Calculate precise costs
        if is_lambda:
            # Lambda pricing: $0.0000002 per request + duration cost
            # Duration: $0.0000166667 per GB-second (x86) or $0.0000133334 per GB-second (ARM)
            memory_gb = 0.512  # 512 MB default
            request_cost = len(book_infos) * 0.0000002
            
            # Use x86 pricing (conservative estimate)
            duration_cost_per_book = avg_time_per_book * memory_gb * 0.0000166667
            total_duration_cost = duration_cost_per_book * len(book_infos)
            total_cost = request_cost + total_duration_cost
            
            print(f"\n💰 AWS Lambda Cost Breakdown:")
            print(f"   • Request cost: ${request_cost:.6f} ({len(book_infos)} × $0.0000002)")
            print(f"   • Duration cost: ${total_duration_cost:.6f} ({avg_time_per_book:.2f}s × {memory_gb}GB × {len(book_infos)} books)")
            print(f"   • Total estimated cost: ${total_cost:.4f}")
            print(f"   • Cost per book: ${total_cost/len(book_infos):.6f}")
            
            # Compare with free tier
            free_requests = 1_000_000
            free_gb_seconds = 400_000
            
            if len(book_infos) <= free_requests:
                used_gb_seconds = avg_time_per_book * memory_gb * len(book_infos)
                if used_gb_seconds <= free_gb_seconds:
                    print(f"   🎉 Completely FREE (within monthly free tier)")
                else:
                    print(f"   ⚠️  Exceeds free GB-seconds ({used_gb_seconds:.0f} > {free_gb_seconds})")
            
        else:
            print(f"\n💻 Local execution: FREE")
            print(f"   • Total time: {total_elapsed/60:.1f} minutes")
            print(f"   • Concurrency: 15 threads")
            print(f"   • Equivalent Lambda cost would be: ${(avg_time_per_book * 0.512 * 0.0000166667 + 0.0000002) * len(book_infos):.4f}")
        
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
        import aiohttp  # noqa: F401
    except ImportError:
        print("⚠️  Installing aiohttp...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    
    exit(asyncio.run(main()))