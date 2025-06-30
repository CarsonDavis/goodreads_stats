so, i was at the point of deployment, but the links seems slightly wrong on prod. there was an issue with me having two index files and a mismatch 

lets reorganize the urls like this. i want a separate html for each page, no spa stuff. let me know if you see any issues with this plan

production internet
goodreads-stats.codebycarson.com - upload/project information
goodreads-stats.codebycarson.com/dashboard?uuid= - dashboard with statistics
goodreads-stats.codebycarson.com/books?uuid=...filters - list of books in a filter
goodreads-stats.codebycarson.com/detail?uuid=...filters - review of a book

local development
localhost:8000 - upload/project information
localhost:8000/dashboard?uuid= - dashboard with statistics
localhost:8000/books?uuid=...filters - list of books in a filter
localhost:8000/detail?uuid=...filters - review of a book



⏺ Perfect plan! I see no major issues with this URL structure. It's clean, RESTful,
  and much better than the SPA approach. Let me implement it:

  Benefits of your plan:
  - ✅ Clear separation of concerns (one HTML per page)
  - ✅ Better SEO and bookmarking
  - ✅ Standard web server behavior (no client-side routing)
  - ✅ CloudFront will handle the /dashboard, /books, /detail paths naturally

  Implementation needed:
  1. Split the current combined index.html into 4 separate files
  2. Update navigation links to use the new paths
  3. Adjust deployment to serve files from root (no /dashboard/ folder nesting)

⏺ Implementation Complete ✅
  ⎿  ✅ Create separate HTML files for each page (index.html, dashboard.html,        
       books.html, detail.html)
     ✅ Remove SPA router logic and split combined HTML
     ✅ Update all internal navigation links to use new URL structure
     ✅ Update GitHub Actions deployment to handle multiple HTML files
     ✅ Update CloudFront configuration for new routing structure
     ✅ Update nginx configuration for local development
     ✅ Update Docker Compose volume mounts
     ✅ Update all documentation files (ARCHITECTURE.md, INFRASTRUCTURE.md, IAC.md, dashboard/README.md)
     