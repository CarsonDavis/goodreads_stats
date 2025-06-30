#!/usr/bin/env python3
"""
Analyze Goodreads library export CSV to understand field completeness and possible values.
"""

import pandas as pd
import sys
from collections import Counter
import numpy as np

def analyze_csv(file_path):
    """Analyze the Goodreads CSV export file."""
    try:
        df = pd.read_csv(file_path)
        print(f"Dataset contains {len(df)} books with {len(df.columns)} fields\n")
        
        print("=" * 60)
        print("FIELD ANALYSIS")
        print("=" * 60)
        
        # Analyze each field
        for col in df.columns:
            print(f"\n📊 {col}")
            print("-" * 40)
            
            # Basic stats
            total_count = len(df)
            non_null_count = df[col].notna().sum()
            non_empty_count = (df[col].astype(str).str.strip() != '').sum()
            completeness = (non_empty_count / total_count) * 100
            
            print(f"Completeness: {non_empty_count}/{total_count} ({completeness:.1f}%)")
            
            # Data type analysis
            sample_values = df[col].dropna().astype(str).str.strip()
            sample_values = sample_values[sample_values != ''].head(5).tolist()
            
            if sample_values:
                print(f"Sample values: {sample_values}")
                
                # Special analysis for key identifying fields
                if col in ['ISBN', 'ISBN13', 'Book Id']:
                    unique_count = df[col].nunique()
                    print(f"Unique values: {unique_count}")
                    
                    if col in ['ISBN', 'ISBN13']:
                        # Check ISBN format patterns
                        isbn_values = df[col].dropna().astype(str)
                        isbn_patterns = Counter()
                        for isbn in isbn_values:
                            clean_isbn = isbn.replace('=', '').replace('"', '').strip()
                            if clean_isbn:
                                isbn_patterns[len(clean_isbn)] += 1
                        print(f"ISBN length patterns: {dict(isbn_patterns)}")
                
                # Analysis for categorical-like fields
                if col in ['Exclusive Shelf', 'Binding', 'Publisher']:
                    value_counts = df[col].value_counts().head(10)
                    print(f"Top values:\n{value_counts}")
                
                # Analysis for rating fields
                if 'Rating' in col:
                    numeric_values = pd.to_numeric(df[col], errors='coerce').dropna()
                    if len(numeric_values) > 0:
                        print(f"Range: {numeric_values.min():.1f} - {numeric_values.max():.1f}")
                        print(f"Mean: {numeric_values.mean():.2f}")
        
        print("\n" + "=" * 60)
        print("KEY FINDINGS FOR API INTEGRATION")
        print("=" * 60)
        
        # Analyze key identifying fields
        key_fields = ['Book Id', 'ISBN', 'ISBN13', 'Title', 'Author']
        
        print("\n🔑 IDENTIFYING FIELDS ANALYSIS:")
        for field in key_fields:
            if field in df.columns:
                non_empty = (df[field].astype(str).str.strip() != '').sum()
                completeness = (non_empty / len(df)) * 100
                unique_ratio = df[field].nunique() / len(df) * 100 if non_empty > 0 else 0
                print(f"{field}: {completeness:.1f}% complete, {unique_ratio:.1f}% unique")
        
        # ISBN analysis for API calls
        print("\n📚 ISBN ANALYSIS FOR API INTEGRATION:")
        isbn_fields = ['ISBN', 'ISBN13']
        for isbn_field in isbn_fields:
            if isbn_field in df.columns:
                clean_isbns = df[isbn_field].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                valid_isbns = clean_isbns[clean_isbns != '']
                print(f"{isbn_field}: {len(valid_isbns)} valid entries ({len(valid_isbns)/len(df)*100:.1f}%)")
                
                if len(valid_isbns) > 0:
                    print(f"  Sample clean ISBNs: {valid_isbns.head(3).tolist()}")
        
        # Books without ISBN
        isbn_missing = df[(df['ISBN'].astype(str).str.replace('=', '').str.replace('"', '').str.strip() == '') & 
                         (df['ISBN13'].astype(str).str.replace('=', '').str.replace('"', '').str.strip() == '')]
        print(f"\n⚠️  Books without ISBN: {len(isbn_missing)} ({len(isbn_missing)/len(df)*100:.1f}%)")
        
        if len(isbn_missing) > 0:
            print("Sample books without ISBN:")
            for _, book in isbn_missing[['Title', 'Author']].head(3).iterrows():
                print(f"  - '{book['Title']}' by {book['Author']}")
        
        print(f"\n💡 RECOMMENDATION:")
        isbn_coverage = len(df) - len(isbn_missing)
        print(f"Use ISBN13 as primary identifier ({isbn_coverage}/{len(df)} books = {isbn_coverage/len(df)*100:.1f}% coverage)")
        print(f"Fall back to Title + Author for remaining {len(isbn_missing)} books")
        
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_goodreads_export.py <csv_file_path>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    sys.exit(analyze_csv(csv_file))