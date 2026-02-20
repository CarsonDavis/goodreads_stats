#!/usr/bin/env python3
"""
Time test: Generate genre JSON for 25 books to estimate full runtime.
"""

import time
from genres import quick_pipeline

def main():
    print("⏱️  TIMING TEST: 25 Books with Genre Enrichment")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        json_path = quick_pipeline(
            csv_path="data/goodreads_library_export-2025.06.15.csv",
            output_path=None,  # Auto UUID filename
            sample_size=25,    # Test with 25 books
            enrich_genres=True
        )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print("\n" + "=" * 60)
        print("✅ TIMING RESULTS")
        print("=" * 60)
        print(f"📊 Books processed: 25")
        print(f"⏱️  Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"📈 Time per book: {elapsed/25:.1f} seconds")
        print(f"📄 JSON saved to: {json_path}")
        
        # Estimate full dataset
        total_books = 762  # Your total book count
        estimated_total = (elapsed / 25) * total_books
        
        print(f"\n🔮 FULL DATASET ESTIMATE:")
        print(f"📚 Total books in CSV: {total_books}")
        print(f"⏱️  Estimated total time: {estimated_total:.0f} seconds")
        print(f"🕐 Estimated time: {estimated_total/3600:.1f} hours")
        print(f"📅 Recommended: Run overnight or during work day")
        
        # Performance analysis
        print(f"\n📊 PERFORMANCE BREAKDOWN:")
        print(f"⚡ Rate limiting: ~1 second between requests")
        print(f"🌐 API calls per book: ~2-3 (Google Books + Open Library)")
        print(f"💾 Processing overhead: ~{(elapsed/25) - 2:.1f} seconds per book")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())