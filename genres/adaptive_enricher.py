"""
Adaptive Genre Enricher - Automatically chooses optimal execution strategy.

Local: Uses async multithreading (15 concurrent)
AWS Lambda: Uses Lambda invocation (1 per book)
"""

import asyncio
import json
import logging
import os
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from .models import BookInfo, EnrichedBook
from .async_genre_enricher import AsyncGenreEnricher


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