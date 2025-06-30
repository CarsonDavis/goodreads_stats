# URL Structure Update

## New Domain Structure

**Production:** goodreads-stats.codebycarson.com
**Development:** goodreads-stats-dev.codebycarson.com

## Updated URL Mapping

### Main Application URLs
- **Upload/Homepage:** `goodreads-stats.codebycarson.com/` (entry point)
- **Dashboard:** `goodreads-stats.codebycarson.com/dashboard/?uuid=...`
- **Books List:** `goodreads-stats.codebycarson.com/dashboard/books?uuid=xxx&type=...`
- **Book Detail:** `goodreads-stats.codebycarson.com/dashboard/detail?id=...&uuid=...`

### API Endpoints
- **Upload:** `goodreads-stats.codebycarson.com/api/upload`
- **Status:** `goodreads-stats.codebycarson.com/api/status/{uuid}`
- **Data:** `goodreads-stats.codebycarson.com/api/data/{uuid}`
- **Delete:** `goodreads-stats.codebycarson.com/api/data/{uuid}` (DELETE)

## Changes Made

1. **Domain Structure:** Changed from `codebycarson.com/goodreads-stats/` to dedicated subdomains
2. **Environment Detection:** Updated JavaScript files to detect new domain patterns
3. **Documentation:** Updated all infrastructure and deployment docs
4. **CORS Configuration:** Updated to support both production and development domains     

