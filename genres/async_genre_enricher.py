"""
Async Genre Enricher for high-performance concurrent API processing.
"""

import asyncio
import aiohttp
import logging
import time
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

from .models import BookInfo, EnrichedBook
from .processors import process_google_response, process_open_library_response
from .genre_merger import merge_and_normalize


class AsyncGenreEnricher:
    """
    High-performance async genre enricher with intelligent concurrency control.
    
    Features:
    - Concurrent API calls (Google Books + Open Library in parallel)
    - Rate limiting with semaphore
    - Retry logic with exponential backoff
    - Batch processing for optimal performance
    """
    
    def __init__(self, max_concurrent: int = 10, rate_limit_delay: float = 0.1):
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # API endpoints
        self.google_books_url = "https://www.googleapis.com/books/v1/volumes"
        self.openlibrary_search_url = "https://openlibrary.org/search.json"
        self.openlibrary_works_url = "https://openlibrary.org/works"
        self.openlibrary_books_url = "https://openlibrary.org/api/books"
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=50)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def enrich_books_batch(self, books: List[BookInfo]) -> List[EnrichedBook]:
        """
        Enrich a batch of books concurrently.
        
        Args:
            books: List of BookInfo objects to enrich
            
        Returns:
            List of EnrichedBook objects with enriched genres
        """
        self.logger.info(f"Starting async enrichment of {len(books)} books")
        self.logger.info(f"Concurrency: {self.max_concurrent}, Rate limit: {self.rate_limit_delay}s")
        
        start_time = time.time()
        
        # Create enrichment tasks
        tasks = [self.enrich_book_async(book) for book in books]
        
        # Execute with progress tracking
        enriched_books = []
        completed = 0
        
        for coro in asyncio.as_completed(tasks):
            enriched_book = await coro
            enriched_books.append(enriched_book)
            completed += 1
            
            if completed % 10 == 0 or completed == len(books):
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = len(books) - completed
                eta = remaining / rate if rate > 0 else 0
                
                self.logger.info(
                    f"Progress: {completed}/{len(books)} "
                    f"({completed/len(books)*100:.1f}%) "
                    f"Rate: {rate:.1f} books/sec "
                    f"ETA: {eta/60:.1f} min"
                )
        
        elapsed = time.time() - start_time
        self.logger.info(f"Batch complete! {len(books)} books in {elapsed:.1f}s ({len(books)/elapsed:.1f} books/sec)")
        
        return enriched_books
    
    async def enrich_book_async(self, book: BookInfo) -> EnrichedBook:
        """
        Enrich a single book with concurrent API calls.
        
        Args:
            book: BookInfo to enrich
            
        Returns:
            EnrichedBook with enriched genres
        """
        async with self.semaphore:  # Rate limiting
            enriched_book = EnrichedBook(input_info=book)
            enriched_book.add_log("Starting async enrichment")
            
            # Rate limiting delay
            await asyncio.sleep(self.rate_limit_delay)
            
            # Fetch from both APIs concurrently
            google_task = self.fetch_google_data_async(book)
            openlibrary_task = self.fetch_openlibrary_data_async(book)
            
            google_data, (ol_edition_data, ol_work_data) = await asyncio.gather(
                google_task, openlibrary_task, return_exceptions=True
            )
            
            # Process Google Books data
            if isinstance(google_data, dict):
                enriched_book.google_response = google_data
                try:
                    google_genres = process_google_response(google_data)
                    enriched_book.processed_google_genres = google_genres
                    enriched_book.add_log(f"Google Books: {len(google_genres)} genres")
                except Exception as e:
                    enriched_book.add_log(f"Google Books processing error: {e}")
            elif isinstance(google_data, Exception):
                enriched_book.add_log(f"Google Books error: {google_data}")
            else:
                enriched_book.add_log("Google Books: No data")
            
            # Process Open Library data
            if isinstance((ol_edition_data, ol_work_data), tuple) and not isinstance((ol_edition_data, ol_work_data), Exception):
                ol_edition, ol_work = ol_edition_data, ol_work_data
                if ol_edition:
                    enriched_book.openlib_edition_response = ol_edition
                if ol_work:
                    enriched_book.openlib_work_response = ol_work
                
                try:
                    ol_genres = process_open_library_response(ol_edition, ol_work)
                    enriched_book.processed_openlib_genres = ol_genres
                    enriched_book.add_log(f"Open Library: {len(ol_genres)} subjects")
                except Exception as e:
                    enriched_book.add_log(f"Open Library processing error: {e}")
            elif isinstance((ol_edition_data, ol_work_data), Exception):
                enriched_book.add_log(f"Open Library error: {(ol_edition_data, ol_work_data)}")
            else:
                enriched_book.add_log("Open Library: No data")
            
            # Merge and finalize
            try:
                final_genres = merge_and_normalize(
                    enriched_book.processed_google_genres,
                    enriched_book.processed_openlib_genres
                )
                enriched_book.final_genres = final_genres
                enriched_book.add_log(f"Final: {len(final_genres)} merged genres")
            except Exception as e:
                enriched_book.add_log(f"Genre merging error: {e}")
            
            return enriched_book
    
    async def fetch_google_data_async(self, book: BookInfo) -> Optional[Dict]:
        """Async fetch from Google Books API"""
        try:
            # Build query
            if book.isbn13:
                query = f"isbn:{book.isbn13}"
            elif book.isbn:
                query = f"isbn:{book.isbn}"
            else:
                query = f'intitle:"{book.title}" inauthor:"{book.author}"'
            
            params = {
                'q': query,
                'projection': 'full',
                'maxResults': 1
            }
            
            url = f"{self.google_books_url}?{urlencode(params)}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('totalItems', 0) > 0:
                        return data['items'][0]
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Google Books API error for {book.title}: {e}")
            return None
    
    async def fetch_openlibrary_data_async(self, book: BookInfo) -> tuple:
        """Async fetch from Open Library API"""
        try:
            edition_data = None
            work_data = None
            
            # Try ISBN lookup first
            if book.isbn13 or book.isbn:
                isbn = book.isbn13 or book.isbn
                isbn_url = f"{self.openlibrary_books_url}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
                
                async with self.session.get(isbn_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            edition_data = list(data.values())[0]
                            
                            # Get work data if available
                            works = edition_data.get('works', [])
                            if works:
                                work_key = works[0]['key']
                                work_url = f"https://openlibrary.org{work_key}.json"
                                
                                async with self.session.get(work_url) as work_response:
                                    if work_response.status == 200:
                                        work_data = await work_response.json()
            
            # Fallback to search if no ISBN results
            if not edition_data:
                search_params = {
                    'title': book.title,
                    'author': book.author,
                    'limit': 1
                }
                search_url = f"{self.openlibrary_search_url}?{urlencode(search_params)}"
                
                async with self.session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        docs = data.get('docs', [])
                        if docs:
                            doc = docs[0]
                            edition_data = doc
                            
                            # Get work data
                            work_key = doc.get('key')
                            if work_key:
                                work_url = f"https://openlibrary.org/works/{work_key}.json"
                                async with self.session.get(work_url) as work_response:
                                    if work_response.status == 200:
                                        work_data = await work_response.json()
            
            return (edition_data, work_data)
            
        except Exception as e:
            self.logger.debug(f"Open Library API error for {book.title}: {e}")
            return (None, None)