# Book API Testing Tool

A comprehensive Python tool for testing and comparing book APIs to supplement Goodreads export data with genre information. Tests Google Books API and OpenLibrary API to determine which provides better genre classification for your book collection.

## Features

- 📚 **Load Goodreads Export**: Automatically parse and clean your Goodreads CSV export
- 🔍 **Multi-API Testing**: Compare Google Books and OpenLibrary APIs
- 📊 **Performance Analysis**: Track response times, success rates, and genre coverage
- 🎯 **Genre Extraction**: Extract detailed genre/subject classifications from each API
- 🐛 **Debug Mode**: Investigate API responses to understand data quality
- 💾 **Results Export**: Save results to CSV and JSON for further analysis

## Quick Start

### 1. Installation

```bash
# Clone or download the code
# Install dependencies
pip install -r requirements.txt
```

### 2. Prepare Your Data

Export your Goodreads library and place the CSV file in the `data/` directory:
```
data/goodreads_library_export-2025.06.15.csv
```

### 3. Run Basic Test

```bash
python -m api.main
```

This will:
- Test 5 sample books from your library
- Compare Google Books vs OpenLibrary APIs
- Display detailed results and recommendations
- Save results to `api/results/`

## Usage Options

### Basic Testing
```bash
python -m api.main          # Full test with 5 books
```

### Debug Mode
```bash
python -m api.main debug    # Debug single book to see raw API data
```

### Load Previous Results
```bash
python -m api.main load     # Display results from previous test
```

### Test with Google Books API Key
```bash
python -m api.main apikey   # Test with your own API key for better results
```

## Getting a Google Books API Key (Optional)

For potentially better results, you can get a free Google Books API key:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the "Books API"
4. Go to "Credentials" → "Create Credentials" → "API Key"
5. Set the key as environment variable:

```bash
export GOOGLE_BOOKS_API_KEY="your_api_key_here"
```

## Expected Results

Based on testing, here's what to expect:

### Google Books API
- ✅ **Reliability**: ~95-100% success rate
- ⚡ **Speed**: ~0.3-0.5 seconds per request
- 📂 **Genre Quality**: 2-8 genres per book with **mainCategory** field providing specific classifications like "Business & Economics / Entrepreneurship"
- 💡 **Best for**: Primary classification, reliable basic categories

### OpenLibrary API  
- ✅ **Reliability**: ~80-90% success rate  
- ⚡ **Speed**: ~0.3-0.4 seconds per request
- 📂 **Genre Quality**: 15-25+ detailed subjects per book
- 💡 **Best for**: Detailed subject tagging, academic classifications

### Recommended Strategy
1. **Primary**: Use Google Books (with `projection=full`) for reliable, specific categories
2. **Secondary**: Use OpenLibrary for additional detailed subject tags
3. **Fallback**: Use title/author search for books without ISBNs (24% of typical Goodreads exports)

## Project Structure

```
api/
├── __init__.py          # Package initialization
├── main.py              # Main execution script
├── models.py            # Data structures (BookInfo, APIResponse)
├── clients.py           # API client implementations
├── tester.py            # Testing orchestrator and analysis
└── results/             # Output directory for results
    ├── api_test_results.csv
    └── api_performance_report.json

data/
└── goodreads_library_export-2025.06.15.csv

requirements.txt         # Python dependencies
README.md               # This file
```

## Key Fixes Applied

This tool addresses the initial issue where Google Books API seemed to only return basic categories like "Fiction". The key improvements:

1. **Always use `projection=full`** - Gets the critical `mainCategory` field
2. **Extract `mainCategory` first** - This contains the most specific classification
3. **Enhanced genre parsing** - Splits hierarchical categories appropriately
4. **Comprehensive debugging** - Shows exactly what each API returns

## Sample Output

```
📚 The Innovators: How a Group of Hackers, Geniuses and Geeks Created the Digital Revolution by Walter Isaacson
────────────────────────────────────────────────────────────────────────────────────────────────────────

  Google Books: ✅ SUCCESS (0.48s)
    📝 Genres found (5):
      • Business & Economics / Entrepreneurship
      • Business & Economics  
      • Entrepreneurship
      • biography
      • Technology

  OpenLibrary: ✅ SUCCESS (0.30s)
    📝 Genres found (25):
      • Computers, history
      • Internet
      • Biographies
      • Technology
      • Innovation
      ... and 20 more
```

## Troubleshooting

### "No genres found" for Google Books
- Ensure you're using `projection=full` parameter
- Try with a Google Books API key
- Check if the book exists on Google Books

### Low success rates
- Check your internet connection
- Verify CSV file format matches Goodreads export
- Some books may not be in the APIs' databases

### Import errors
- Ensure you're running from the project root directory
- Install all requirements: `pip install -r requirements.txt`

## Contributing

Feel free to add support for additional book APIs like:
- WorldCat Search API
- Library of Congress API  
- Crossref API
- ISBNdb API

The modular design makes it easy to add new `BookAPIClient` implementations.