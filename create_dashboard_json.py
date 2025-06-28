#!/usr/bin/env python3
"""
Complete pipeline demo: CSV -> Genre Enrichment -> Final Dashboard JSON

This script demonstrates the full workflow:
1. Load Goodreads CSV into analytics-ready format
2. Enrich genres via Google Books + Open Library APIs  
3. Export final JSON optimized for dashboard consumption
"""

import logging
import sys
from pathlib import Path

from genres.integrated_pipeline import IntegratedBookPipeline, quick_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    print("📚 GOODREADS DASHBOARD DATA PIPELINE")
    print("=" * 60)
    print("Workflow: CSV → Genre Enrichment → Analytics → Dashboard JSON")
    print()
    
    # Configuration
    csv_path = "data/goodreads_library_export-2025.06.15.csv"
    output_path = "dashboard_data/books.json"
    
    # Check if CSV exists
    if not Path(csv_path).exists():
        print(f"❌ CSV file not found: {csv_path}")
        print("Place your Goodreads export at the path above")
        return 1
    
    try:
        print("🚀 DEMO MODE: Processing 5 books with genre enrichment")
        print("(For full processing, modify sample_size in the script)")
        print()
        
        # Run the complete pipeline (small sample for demo)
        json_path = quick_pipeline(
            csv_path=csv_path,
            output_path=output_path,
            sample_size=5,  # Small sample for demo
            enrich_genres=True  # Enable genre enrichment
        )
        
        print()
        print("=" * 60)
        print("✅ PIPELINE COMPLETE!")
        print(f"📄 Dashboard JSON saved to: {json_path}")
        print()
        print("Next steps:")
        print("1. Inspect the generated JSON structure")
        print("2. Build your dashboard to consume this JSON")
        print("3. For production, increase sample_size or remove it entirely")
        print()
        
        # Show a preview of the generated JSON
        preview_json_structure(json_path)
        
        return 0
        
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        return 1


def preview_json_structure(json_path: str):
    """Show a preview of the generated JSON structure"""
    import json
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        print("📋 JSON STRUCTURE PREVIEW:")
        print("-" * 40)
        
        # Show top-level structure
        print(f"Top-level keys: {list(data.keys())}")
        
        # Show summary stats
        if "summary" in data:
            summary = data["summary"]
            print(f"Books processed: {summary.get('total_books', 0)}")
            print(f"Books with genres: {summary.get('genre_enriched_books', 0)}")
            print(f"Genre enrichment rate: {summary.get('genre_enrichment_rate', 0):.1f}%")
            print(f"Unique genres found: {summary.get('unique_genres', 0)}")
        
        # Show sample book structure
        if "books" in data and data["books"]:
            sample_book = data["books"][0]
            print(f"\nSample book fields: {list(sample_book.keys())}")
            print(f"Sample book: '{sample_book.get('title', 'Unknown')}'")
            print(f"  Author: {sample_book.get('author', 'Unknown')}")
            print(f"  Genres: {sample_book.get('genres', [])}")
            print(f"  Reading date: {sample_book.get('date_read', 'None')}")
            print(f"  Rating: {sample_book.get('my_rating', 'Unrated')}")
        
        # Show metadata if present
        if "metadata" in data:
            metadata = data["metadata"]
            print(f"\nExport timestamp: {metadata.get('export_timestamp', 'Unknown')}")
            print(f"Schema version: {metadata.get('data_schema_version', 'Unknown')}")
        
    except Exception as e:
        print(f"Could not preview JSON: {e}")


def full_production_example():
    """
    Example of how to run the full pipeline for production use.
    Uncomment and modify as needed.
    """
    # pipeline = IntegratedBookPipeline(rate_limit=0.5)  # Slower rate for production
    # 
    # json_path = pipeline.process_csv_to_dashboard_json(
    #     csv_path="data/goodreads_library_export-2025.06.15.csv",
    #     output_json_path="dashboard_data/complete_books.json",
    #     sample_size=None,  # Process all books
    #     include_unread=False,  # Only read books for time-series
    #     enrich_genres=True  # Full genre enrichment
    # )
    # 
    # print(f"Production dashboard JSON: {json_path}")


if __name__ == "__main__":
    sys.exit(main())