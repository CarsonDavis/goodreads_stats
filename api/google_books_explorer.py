# api/google_books_explorer.py
"""
Fresh analysis of Google Books API fields and capabilities.
"""

import requests
import json
import pandas as pd
import re
from typing import Dict, Any, List, Optional


class GoogleBooksExplorer:
    """Explore Google Books API to understand available fields"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/books/v1/volumes"
    
    def search_book(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search for books and return raw API response"""
        params = {
            "q": query,
            "maxResults": max_results,
            "projection": "full"  # Get all available data
        }
        
        if self.api_key:
            params["key"] = self.api_key
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_book_fields(self, api_response: Dict[str, Any]) -> None:
        """Analyze all fields present in API response"""
        if "error" in api_response:
            print(f"❌ Error: {api_response['error']}")
            return
        
        if not api_response.get("items"):
            print("❌ No items found in response")
            return
        
        print(f"📚 Found {len(api_response['items'])} book(s)")
        print("=" * 80)
        
        for i, item in enumerate(api_response["items"]):
            print(f"\n📖 BOOK {i+1}")
            print("-" * 40)
            
            # Top-level fields
            print("🔍 Top-level fields:")
            for key in item.keys():
                print(f"   • {key}")
            
            # Volume info breakdown
            volume_info = item.get("volumeInfo", {})
            if volume_info:
                print(f"\n📝 volumeInfo fields ({len(volume_info)} total):")
                for key, value in volume_info.items():
                    value_type = type(value).__name__
                    if isinstance(value, list):
                        value_preview = f"[{len(value)} items]"
                    elif isinstance(value, str) and len(value) > 50:
                        value_preview = f'"{value[:50]}..."'
                    else:
                        value_preview = repr(value)
                    
                    print(f"   • {key} ({value_type}): {value_preview}")
            
            # Sale info
            sale_info = item.get("saleInfo", {})
            if sale_info:
                print(f"\n💰 saleInfo fields ({len(sale_info)} total):")
                for key, value in sale_info.items():
                    print(f"   • {key}: {repr(value)}")
            
            # Access info  
            access_info = item.get("accessInfo", {})
            if access_info:
                print(f"\n🔐 accessInfo fields ({len(access_info)} total):")
                for key, value in access_info.items():
                    print(f"   • {key}: {repr(value)}")
            
            print("\n" + "="*80)
    
    def analyze_genre_fields(self, api_response: Dict[str, Any]) -> None:
        """Focus specifically on genre/category related fields"""
        if "error" in api_response or not api_response.get("items"):
            print("❌ No valid response to analyze")
            return
        
        print("🎭 GENRE/CATEGORY ANALYSIS")
        print("=" * 60)
        
        all_main_categories = set()
        all_categories = set()
        
        for i, item in enumerate(api_response["items"]):
            volume_info = item.get("volumeInfo", {})
            
            print(f"\n📖 Book {i+1}: {volume_info.get('title', 'Unknown')}")
            print("-" * 40)
            
            # Main category
            main_category = volume_info.get("mainCategory")
            print(f"🎯 mainCategory: {main_category}")
            if main_category:
                all_main_categories.add(main_category)
            
            # Categories array
            categories = volume_info.get("categories", [])
            print(f"📂 categories: {categories}")
            for cat in categories:
                all_categories.add(cat)
            
            # Maturity rating
            maturity = volume_info.get("maturityRating")
            print(f"🔞 maturityRating: {maturity}")
            
            # Check for any other potentially relevant fields
            other_fields = {
                "subjects": volume_info.get("subjects"),
                "contentVersion": volume_info.get("contentVersion"),
                "printType": volume_info.get("printType"),
            }
            
            for field, value in other_fields.items():
                if value:
                    print(f"📋 {field}: {value}")
        
        # Summary
        print(f"\n📊 SUMMARY")
        print("-" * 30)
        print(f"Unique mainCategories found: {len(all_main_categories)}")
        for cat in sorted(all_main_categories):
            print(f"   • {cat}")
        
        print(f"\nUnique categories found: {len(all_categories)}")
        for cat in sorted(all_categories):
            print(f"   • {cat}")
    
    def test_different_queries(self, book_queries: List[str]) -> None:
        """Test different query types to see what data we get"""
        print("🔍 TESTING DIFFERENT QUERY TYPES")
        print("=" * 60)
        
        for query in book_queries:
            print(f"\n🔎 Query: {query}")
            print("-" * 40)
            
            response = self.search_book(query, max_results=3)
            
            if "error" in response:
                print(f"❌ Error: {response['error']}")
                continue
            
            if not response.get("items"):
                print("❌ No results found")
                continue
            
            # Quick summary of what we found
            for i, item in enumerate(response["items"]):
                volume_info = item.get("volumeInfo", {})
                title = volume_info.get("title", "Unknown")
                main_cat = volume_info.get("mainCategory", "None")
                categories = volume_info.get("categories", [])
                
                print(f"   📚 {i+1}. {title}")
                print(f"      🎯 mainCategory: {main_cat}")
                print(f"      📂 categories: {categories}")
    
    def load_goodreads_sample_and_test(self, csv_path: str, sample_size: int = 3) -> None:
        """Load some books from Goodreads CSV and test Google Books API"""
        try:
            df = pd.read_csv(csv_path)
            sample = df.sample(n=min(sample_size, len(df)), random_state=42)
            
            print(f"📖 TESTING WITH {len(sample)} GOODREADS BOOKS")
            print("=" * 60)
            
            for _, row in sample.iterrows():
                title = row["Title"]
                author = row["Author"]
                isbn13 = self._clean_isbn(row.get("ISBN13", ""))
                
                print(f"\n📚 Testing: {title} by {author}")
                print(f"ISBN13: {isbn13 or 'None'}")
                print("-" * 50)
                
                # Try different query approaches
                queries = []
                if isbn13:
                    queries.append(f"isbn:{isbn13}")
                queries.append(f'intitle:"{title}" inauthor:"{author}"')
                queries.append(f'"{title}" "{author}"')
                
                best_response = None
                for query in queries:
                    print(f"🔎 Trying: {query}")
                    response = self.search_book(query, max_results=1)
                    
                    if response.get("items"):
                        best_response = response
                        print(f"   ✅ Found {response['totalItems']} results")
                        break
                    else:
                        print(f"   ❌ No results")
                
                if best_response:
                    self.analyze_genre_fields(best_response)
                else:
                    print("   ⚠️ No successful queries for this book")
                
                print("\n" + "="*80)
                
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
    
    def _clean_isbn(self, isbn_str: str) -> str:
        """Clean ISBN from Excel formatting"""
        if not isbn_str or pd.isna(isbn_str):
            return ""
        
        # Remove Excel formula formatting
        clean_isbn = re.sub(r'^="?([0-9X]+)"?$', r"\1", str(isbn_str))
        
        # Remove any non-alphanumeric characters except X
        clean_isbn = re.sub(r"[^0-9X]", "", clean_isbn.upper())
        
        # Validate length
        if len(clean_isbn) in [10, 13]:
            return clean_isbn
        
        return ""


def main():
    """Main exploration function"""
    explorer = GoogleBooksExplorer()
    
    print("🔍 GOOGLE BOOKS API FIELD EXPLORATION")
    print("=" * 60)
    
    # Test some well-known books
    test_queries = [
        "isbn:9780547928227",  # The Hobbit
        'intitle:"Dune" inauthor:"Herbert"',
        "The Great Gatsby",
        "Science Fiction",
    ]
    
    explorer.test_different_queries(test_queries)
    
    # Test with actual Goodreads data
    csv_path = "data/goodreads_library_export-2025.06.15.csv"
    print(f"\n\n🔍 TESTING WITH ACTUAL GOODREADS DATA")
    explorer.load_goodreads_sample_and_test(csv_path, sample_size=5)


if __name__ == "__main__":
    main()