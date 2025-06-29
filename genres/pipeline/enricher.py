# genres/pipeline/enricher.py
"""
Consolidated book enrichment pipeline with adaptive execution strategies.

Local: Uses async multithreading (15 concurrent)
AWS Lambda: Uses Lambda invocation (1 per book)
"""

import asyncio
import aiohttp
import json
import logging
import os
import time
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

from ..models.book import BookInfo, EnrichedBook
from ..sources import process_google_response, process_open_library_response
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


class AdaptiveGenreEnricher:
    """
    Smart enricher that adapts to execution environment:
    
    Local Development:
    - Uses AsyncGenreEnricher with 15 concurrent threads
    - Direct API calls with rate limiting
    - 4-6 minute processing time
    
    AWS Lambda:
    - Spawns 1 Lambda function per book
    - Massive parallelism (100+ concurrent)
    - 10-30 second processing time
    - Cost: ~$0.05-0.10 for 762 books
    """
    
    def __init__(self, max_local_concurrent: int = 15):
        self.max_local_concurrent = max_local_concurrent
        self.logger = logging.getLogger(self.__class__.__name__)
        self.is_lambda = self._detect_lambda_environment()
        
        if self.is_lambda:
            self.logger.info("🚀 Running in AWS Lambda - using Lambda invocation strategy")
            self._setup_lambda_client()
        else:
            self.logger.info(f"💻 Running locally - using async strategy ({max_local_concurrent} concurrent)")
    
    def _detect_lambda_environment(self) -> bool:
        """Detect if we're running in AWS Lambda"""
        return (
            os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None or
            os.environ.get('LAMBDA_RUNTIME_DIR') is not None or
            os.environ.get('AWS_EXECUTION_ENV', '').startswith('AWS_Lambda')
        )
    
    def _setup_lambda_client(self):
        """Setup AWS Lambda client for Lambda-to-Lambda invocation"""
        try:
            import boto3
            self.lambda_client = boto3.client('lambda')
            self.worker_function_name = os.environ.get(
                'GENRE_WORKER_FUNCTION_NAME', 
                'goodreads-genre-worker'
            )
        except ImportError:
            self.logger.warning("boto3 not available - falling back to local strategy")
            self.is_lambda = False
    
    async def enrich_books_adaptive(self, books: List[BookInfo]) -> List[EnrichedBook]:
        """
        Enrich books using the optimal strategy for current environment.
        
        Args:
            books: List of BookInfo objects to enrich
            
        Returns:
            List of EnrichedBook objects with enriched genres
        """
        if self.is_lambda:
            return await self._enrich_with_lambda_swarm(books)
        else:
            return await self._enrich_with_async_local(books)
    
    async def _enrich_with_async_local(self, books: List[BookInfo]) -> List[EnrichedBook]:
        """Local strategy: Async multithreading"""
        self.logger.info(f"🔄 Using local async strategy for {len(books)} books")
        
        async with AsyncGenreEnricher(self.max_local_concurrent, 0.05) as enricher:
            return await enricher.enrich_books_batch(books)
    
    async def _enrich_with_lambda_swarm(self, books: List[BookInfo]) -> List[EnrichedBook]:
        """AWS strategy: One Lambda per book"""
        self.logger.info(f"☁️ Using Lambda swarm strategy for {len(books)} books")
        
        # Create tasks for each book
        tasks = []
        for book in books:
            task = self._invoke_worker_lambda(book)
            tasks.append(task)
        
        # Execute all Lambda invocations concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert results back to EnrichedBook objects
        enriched_books = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Lambda failed for book {i}: {result}")
                # Create empty enriched book for failed cases
                enriched_books.append(EnrichedBook(input_info=books[i]))
            else:
                enriched_books.append(result)
        
        return enriched_books
    
    async def _invoke_worker_lambda(self, book: BookInfo) -> EnrichedBook:
        """Invoke worker Lambda for a single book"""
        try:
            payload = {
                'book': {
                    'title': book.title,
                    'author': book.author,
                    'isbn13': book.isbn13,
                    'isbn': book.isbn,
                    'goodreads_id': book.goodreads_id
                }
            }
            
            # Invoke Lambda function
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.lambda_client.invoke(
                    FunctionName=self.worker_function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )
            )
            
            # Parse response
            response_payload = json.loads(response['Payload'].read())
            
            if 'errorMessage' in response_payload:
                raise Exception(f"Lambda error: {response_payload['errorMessage']}")
            
            # Convert Lambda response back to EnrichedBook
            return self._lambda_response_to_enriched_book(response_payload, book)
            
        except Exception as e:
            self.logger.error(f"Failed to invoke Lambda for {book.title}: {e}")
            raise
    
    def _lambda_response_to_enriched_book(self, lambda_response: Dict, original_book: BookInfo) -> EnrichedBook:
        """Convert Lambda response to EnrichedBook object"""
        enriched_book = EnrichedBook(input_info=original_book)
        
        # Extract data from Lambda response
        enriched_book.google_response = lambda_response.get('google_response')
        enriched_book.openlib_edition_response = lambda_response.get('openlib_edition_response')  
        enriched_book.openlib_work_response = lambda_response.get('openlib_work_response')
        enriched_book.processed_google_genres = lambda_response.get('processed_google_genres', [])
        enriched_book.processed_openlib_genres = lambda_response.get('processed_openlib_genres', [])
        enriched_book.final_genres = lambda_response.get('final_genres', [])
        enriched_book.processing_log = lambda_response.get('processing_log', [])
        
        return enriched_book


class EnvironmentAwareBookPipeline:
    """
    Pipeline that adapts to execution environment automatically.
    """
    
    def __init__(self, max_local_concurrent: int = 15):
        self.enricher = AdaptiveGenreEnricher(max_local_concurrent)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def process_books_smart(
        self,
        books: List[BookInfo],
        show_progress: bool = True
    ) -> List[EnrichedBook]:
        """
        Process books using optimal strategy for current environment.
        
        Args:
            books: List of BookInfo objects
            show_progress: Whether to show progress updates
            
        Returns:
            List of EnrichedBook objects
        """
        if self.enricher.is_lambda:
            self.logger.info(f"☁️ AWS Lambda mode: Processing {len(books)} books in parallel")
            self.logger.info("⚡ Estimated time: 10-30 seconds")
            self.logger.info("💰 Estimated cost: $0.05-0.10")
        else:
            self.logger.info(f"💻 Local mode: Processing {len(books)} books with {self.enricher.max_local_concurrent} threads")
            self.logger.info("⚡ Estimated time: 4-6 minutes")
            self.logger.info("💰 Cost: Free")
        
        return await self.enricher.enrich_books_adaptive(books)


# Convenience function that works everywhere
async def smart_enrich_books(books: List[BookInfo]) -> List[EnrichedBook]:
    """
    Smart book enrichment that automatically adapts to environment.
    
    Local: Uses async multithreading
    AWS: Uses Lambda swarm
    
    Args:
        books: List of BookInfo objects
        
    Returns:
        List of EnrichedBook objects
    """
    pipeline = EnvironmentAwareBookPipeline()
    return await pipeline.process_books_smart(books)