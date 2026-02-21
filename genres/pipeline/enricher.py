# genres/pipeline/enricher.py
"""
Async book genre enrichment pipeline.

Provides AsyncGenreEnricher for concurrent genre lookups using
Goodreads scraping (primary) with Google Books + Open Library fallback.
"""

import asyncio
import aiohttp
import logging
import time
from typing import List, Optional, Dict
from urllib.parse import urlencode

from ..models.book import BookInfo, EnrichedBook
from ..sources import process_google_response, process_open_library_response
from ..sources.goodreads import fetch_goodreads_genres
from ..utils import merge_and_normalize


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
        
        # Execute while preserving order (this is critical!)
        enriched_books = await asyncio.gather(*tasks)
        
        completed = len(books)
        
        elapsed = time.time() - start_time
        self.logger.info(f"Batch complete! {len(books)} books in {elapsed:.1f}s ({len(books)/elapsed:.1f} books/sec)")
        
        return enriched_books
    
    async def enrich_book_async(self, book: BookInfo) -> EnrichedBook:
        """
        Enrich a single book with genre data.

        Uses Goodreads scraping as the primary source, falling back to
        Google Books + Open Library APIs when scraping fails.

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

            # PRIMARY: Try Goodreads scraping first
            goodreads_genres = []
            if book.goodreads_id:
                goodreads_genres = await self.fetch_goodreads_genres_async(book)
                enriched_book.processed_goodreads_genres = goodreads_genres

                if goodreads_genres:
                    enriched_book.goodreads_scrape_success = True
                    enriched_book.add_log(f"Goodreads: {len(goodreads_genres)} genres (primary)")
                else:
                    enriched_book.add_log("Goodreads: No genres found")
            else:
                enriched_book.add_log("Goodreads: No goodreads_id available")

            # If Goodreads succeeded, use those genres directly
            if goodreads_genres:
                enriched_book.final_genres = goodreads_genres
                enriched_book.add_log(f"Final: {len(goodreads_genres)} genres from Goodreads")

                # Still fetch Google Books for thumbnails (but not for genres)
                await self._fetch_thumbnails_only(book, enriched_book)

                return enriched_book

            # FALLBACK: Use API sources when Goodreads fails
            enriched_book.add_log("Using API fallback (Google Books + Open Library)")

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

                    # Extract thumbnails from Google Books response
                    items = google_data.get("items", [])
                    if items:
                        volume_info = items[0].get("volumeInfo", {})
                        image_links = volume_info.get("imageLinks", {})

                        enriched_book.thumbnail_url = image_links.get("thumbnail")
                        enriched_book.small_thumbnail_url = image_links.get("smallThumbnail")

                        if enriched_book.thumbnail_url or enriched_book.small_thumbnail_url:
                            enriched_book.add_log("Google Books: Thumbnails extracted")
                        else:
                            enriched_book.add_log("Google Books: No thumbnails available")

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
                enriched_book.add_log(f"Final: {len(final_genres)} merged genres (API fallback)")
            except Exception as e:
                enriched_book.add_log(f"Genre merging error: {e}")

            return enriched_book

    async def fetch_goodreads_genres_async(self, book: BookInfo) -> List[str]:
        """
        Fetch genres from Goodreads via web scraping.

        Args:
            book: BookInfo with goodreads_id

        Returns:
            List of genre strings, empty if scraping fails
        """
        if not book.goodreads_id:
            return []

        return await fetch_goodreads_genres(self.session, book.goodreads_id)

    async def _fetch_thumbnails_only(self, book: BookInfo, enriched_book: EnrichedBook) -> None:
        """
        Fetch thumbnails from Google Books without processing genres.

        Used when Goodreads genres are available but we still want book covers.
        """
        try:
            google_data = await self.fetch_google_data_async(book)
            if isinstance(google_data, dict):
                enriched_book.google_response = google_data
                items = google_data.get("items", [])
                if items:
                    volume_info = items[0].get("volumeInfo", {})
                    image_links = volume_info.get("imageLinks", {})

                    enriched_book.thumbnail_url = image_links.get("thumbnail")
                    enriched_book.small_thumbnail_url = image_links.get("smallThumbnail")

                    if enriched_book.thumbnail_url or enriched_book.small_thumbnail_url:
                        enriched_book.add_log("Google Books: Thumbnails extracted")
        except Exception as e:
            self.logger.debug(f"Thumbnail fetch failed for {book.title}: {e}")
    
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
                        return data  # Return full response, not just first item
            
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
                            edition_data = data  # Pass full response to processor
                            
                            # Get work data if available  
                            first_book = list(edition_data.values())[0] if edition_data else {}
                            works = first_book.get('works', [])
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
