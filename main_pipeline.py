# main_pipeline.py
"""
Main script for running the Book Data Enrichment Pipeline.
"""

from genres.pipeline import BookDataOrchestrator


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