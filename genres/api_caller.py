# genres/api_caller.py
"""
Resilient API caller with rate limiting and retry logic.
"""

import requests
import time
import logging
from typing import Dict, Optional, Tuple


class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0

    def wait(self):
        elapsed = time.time() - self.last_called
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_called = time.time()


class APICaller:
    """
    Resilient API caller that handles rate limiting, retries, and error handling.
    """
    
    def __init__(self, rate_limit: float = 1.0, max_retries: int = 3):
        self.rate_limiter = RateLimiter(rate_limit)
        self.max_retries = max_retries
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get(self, url: str, params: Optional[Dict] = None, timeout: int = 10) -> Tuple[bool, int, Optional[Dict]]:
        """
        Make HTTP GET request with retries and exponential backoff.
        
        Returns:
            (success: bool, status_code: int, response_data: Optional[Dict])
        """
        for attempt in range(self.max_retries):
            self.rate_limiter.wait()
            
            try:
                response = requests.get(url, params=params, timeout=timeout)
                
                # Success cases
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return True, response.status_code, data
                    except ValueError:
                        self.logger.warning(f"Invalid JSON response from {url}")
                        return False, response.status_code, None
                
                # Client errors (4xx) - don't retry
                elif 400 <= response.status_code < 500:
                    self.logger.warning(f"Client error {response.status_code} for {url}")
                    return False, response.status_code, None
                
                # Server errors (5xx) - retry
                elif response.status_code >= 500:
                    self.logger.warning(f"Server error {response.status_code} for {url}, attempt {attempt + 1}")
                    if attempt < self.max_retries - 1:
                        self._backoff_sleep(attempt)
                        continue
                    else:
                        return False, response.status_code, None
                
                # Other status codes
                else:
                    self.logger.warning(f"Unexpected status {response.status_code} for {url}")
                    return False, response.status_code, None
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout for {url}, attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    self._backoff_sleep(attempt)
                    continue
                else:
                    return False, 0, None
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    self._backoff_sleep(attempt)
                    continue
                else:
                    return False, 0, None
        
        return False, 0, None
    
    def _backoff_sleep(self, attempt: int) -> None:
        """Sleep with exponential backoff"""
        sleep_time = 2 ** attempt  # 1s, 2s, 4s, 8s, etc.
        self.logger.info(f"Backing off for {sleep_time}s")
        time.sleep(sleep_time)