# genres/utils/__init__.py
"""
Utility functions for the book genre enrichment pipeline.
"""

from .genre_merger import merge_and_normalize, analyze_genre_overlap

__all__ = [
    "merge_and_normalize",
    "analyze_genre_overlap"
]