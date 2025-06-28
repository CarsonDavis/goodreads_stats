# genres/processors/open_library_processor.py
"""
Open Library API response processor.
"""

from typing import List, Dict, Optional


def process_open_library_response(edition_data: Optional[Dict], work_data: Optional[Dict]) -> List[str]:
    """
    Extract subjects from Open Library Edition and Work responses.
    
    Args:
        edition_data: Raw JSON response from Edition API
        work_data: Raw JSON response from Work API
    
    Returns:
        Combined and deduplicated list of subjects
    """
    subjects = set()
    
    # Process Edition data
    if edition_data:
        edition_subjects = _extract_subjects_from_edition(edition_data)
        subjects.update(edition_subjects)
    
    # Process Work data
    if work_data:
        work_subjects = _extract_subjects_from_work(work_data)
        subjects.update(work_subjects)
    
    return list(subjects)


def _extract_subjects_from_edition(edition_data: Dict) -> List[str]:
    """Extract subjects from Edition API response"""
    subjects = []
    
    # Edition data is usually a dict with ISBN keys
    for book_data in edition_data.values():
        if isinstance(book_data, dict):
            book_subjects = book_data.get("subjects", [])
            for subject in book_subjects:
                if isinstance(subject, dict):
                    name = subject.get("name", "")
                else:
                    name = str(subject)
                
                if name and name.strip():
                    subjects.append(name.strip())
    
    return subjects


def _extract_subjects_from_work(work_data: Dict) -> List[str]:
    """Extract subjects from Work API response"""
    subjects = []
    
    work_subjects = work_data.get("subjects", [])
    for subject in work_subjects:
        if subject and subject.strip():
            subjects.append(subject.strip())
    
    return subjects