#!/usr/bin/env python3
import logging
import time
from genres import quick_pipeline

# Configure logging to show progress
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

print("🚀 Starting FULL dataset genre enrichment...")
print("📚 Processing all books in CSV (estimated 37 minutes)")
print("=" * 60)

start_time = time.time()

# Process ALL 762 books
json_path = quick_pipeline(
    csv_path="data/goodreads_library_export-2025.06.15.csv",
    output_path=None,  # Auto-generates UUID filename
    sample_size=None,  # ALL BOOKS - this is the key change
    enrich_genres=True,
)

elapsed = time.time() - start_time

print("\n" + "=" * 60)
print("✅ COMPLETE!")
print(f"⏱️  Total time: {elapsed/60:.1f} minutes")
print(f"📄 Dashboard JSON: {json_path}")
print("\n🌐 Get dashboard URL:")
print("python get_dashboard_url.py")
