# genres/genre_merger.py
"""
Genre merging and normalization for the Book Data Enrichment Pipeline.
"""

from typing import List


def merge_and_normalize(google_genres: List[str], openlib_genres: List[str]) -> List[str]:
    """
    Merge and normalize genres from Google Books and Open Library.
    
    Steps:
    1. Combine both lists
    2. Remove duplicates (case-insensitive)
    3. Clean and normalize format
    4. Sort for consistency
    
    Args:
        google_genres: Genres from Google Books
        openlib_genres: Subjects from Open Library
    
    Returns:
        Final merged and normalized genre list
    """
    # Combine all genres
    all_genres = google_genres + openlib_genres
    
    # Normalize and deduplicate
    normalized_genres = set()
    
    for genre in all_genres:
        if genre and genre.strip():
            # Basic cleaning
            clean_genre = genre.strip()
            
            # Remove common prefixes that add noise
            prefixes_to_remove = [
                "nyt:",
                "New York Times",
            ]
            
            for prefix in prefixes_to_remove:
                if clean_genre.startswith(prefix):
                    clean_genre = clean_genre[len(prefix):].strip()
                    clean_genre = clean_genre.lstrip("=:- ")
            
            # Skip very short or obviously non-genre entries
            if len(clean_genre) < 2:
                continue
                
            # Skip date-like entries
            if clean_genre.isdigit() or clean_genre.endswith(" century"):
                continue
            
            # Add to normalized set (case-insensitive deduplication)
            if clean_genre:
                # Find if we already have this genre in a different case
                existing_genre = None
                for existing in normalized_genres:
                    if existing.lower() == clean_genre.lower():
                        existing_genre = existing
                        break
                
                if existing_genre:
                    # Keep the version with better capitalization
                    # Prefer title case over all caps or all lowercase
                    if clean_genre.istitle() and not existing_genre.istitle():
                        normalized_genres.remove(existing_genre)
                        normalized_genres.add(clean_genre)
                else:
                    normalized_genres.add(clean_genre)
    
    # Return sorted list for consistency
    return sorted(list(normalized_genres))


def analyze_genre_overlap(google_genres: List[str], openlib_genres: List[str]) -> dict:
    """
    Analyze the overlap between Google Books and Open Library genres.
    
    Returns:
        Dictionary with overlap analysis
    """
    google_set = {g.lower() for g in google_genres}
    openlib_set = {g.lower() for g in openlib_genres}
    
    overlap = google_set.intersection(openlib_set)
    google_only = google_set - openlib_set
    openlib_only = openlib_set - google_set
    
    return {
        "total_genres": len(google_set.union(openlib_set)),
        "google_count": len(google_set),
        "openlib_count": len(openlib_set),
        "overlap_count": len(overlap),
        "overlap_percentage": len(overlap) / len(google_set.union(openlib_set)) * 100 if google_set.union(openlib_set) else 0,
        "google_only": list(google_only),
        "openlib_only": list(openlib_only),
        "overlapping": list(overlap)
    }