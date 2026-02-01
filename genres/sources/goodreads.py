# genres/sources/goodreads.py
"""
Goodreads genre scraping source.

Fetches genres directly from Goodreads book pages using web scraping.
This is the primary genre source due to high-quality, community-curated genres.
"""

import asyncio
import random
import logging
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

GOODREADS_URL = "https://www.goodreads.com/book/show/{book_id}"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

logger = logging.getLogger(__name__)


async def fetch_goodreads_genres(
    session: aiohttp.ClientSession,
    goodreads_id: str,
    max_retries: int = 3,
) -> List[str]:
    """
    Fetch genres for a single book from Goodreads.

    Uses exponential backoff with jitter on failure.
    Returns empty list if all retries fail.

    Args:
        session: aiohttp ClientSession to use for requests
        goodreads_id: The Goodreads book ID
        max_retries: Maximum number of retry attempts

    Returns:
        List of genre strings, empty if scraping fails
    """
    if not goodreads_id:
        return []

    url = GOODREADS_URL.format(book_id=goodreads_id)
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(max_retries):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    genres = parse_goodreads_genres(html)
                    if genres:
                        logger.debug(f"Goodreads {goodreads_id}: found {len(genres)} genres")
                        return genres
                    else:
                        logger.debug(f"Goodreads {goodreads_id}: no genres found in HTML")
                        # Page loaded but no genres - don't retry
                        return []
                elif response.status == 429:
                    # Rate limited - wait longer with exponential backoff
                    wait = (2 ** attempt) + random.uniform(1, 3)
                    logger.debug(f"Goodreads {goodreads_id}: rate limited, waiting {wait:.1f}s")
                    await asyncio.sleep(wait)
                elif response.status == 404:
                    # Book not found - don't retry
                    logger.debug(f"Goodreads {goodreads_id}: 404 not found")
                    return []
                else:
                    # Other error - brief backoff
                    logger.debug(f"Goodreads {goodreads_id}: status {response.status}")
                    await asyncio.sleep(0.5 * (attempt + 1))
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            wait = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
            logger.debug(f"Goodreads {goodreads_id}: error {e}, waiting {wait:.1f}s")
            await asyncio.sleep(wait)

    logger.debug(f"Goodreads {goodreads_id}: all retries failed")
    return []  # All retries failed


# Format-based entries to exclude (not actual genres)
EXCLUDED_GENRES = {
    "audiobook",
    "audiobooks",
    "audio book",
    "audio books",
    "audible",
}


def parse_goodreads_genres(html: str) -> List[str]:
    """
    Extract genre list from Goodreads book page HTML.

    Attempts to find genres using the modern Goodreads page structure,
    falling back to older page structure if needed.

    Args:
        html: Raw HTML content from Goodreads book page

    Returns:
        List of genre strings (deduplicated, preserving order)
    """
    soup = BeautifulSoup(html, "lxml")

    genres = []

    # Primary selector: Modern Goodreads uses data-testid for genre buttons
    genre_elements = soup.select('[data-testid="genresList"] a[href*="/genres/"]')

    for el in genre_elements:
        genre = el.get_text(strip=True)
        if genre and genre not in genres and genre.lower() not in EXCLUDED_GENRES:
            genres.append(genre)

    # Fallback: Try older page structure if no genres found
    if not genres:
        for link in soup.select('a[href*="/genres/"]'):
            genre = link.get_text(strip=True)
            # Filter out non-genre links (navigation, etc.) by length
            if genre and genre not in genres and len(genre) < 50 and genre.lower() not in EXCLUDED_GENRES:
                genres.append(genre)

    return genres
