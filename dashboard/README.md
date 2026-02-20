# 📚 Modern Reading Dashboard

A beautiful, modern dashboard built with vanilla JavaScript to visualize your Goodreads reading data.

## Features

- **📊 Interactive Charts**: Books by year, rating distribution, top genres, pages timeline
- **🌙 Dark Mode**: Automatic theme switching with localStorage persistence
- **📱 Responsive Design**: Works on desktop, tablet, and mobile
- **⚡ Fast Loading**: Pure JavaScript, no framework overhead
- **🔄 Dual Environment**: Local development + production S3 support

## Local Development

1. **Generate your data**:
   ```bash
   python create_dashboard_json.py
   ```
   This creates a JSON file in `dashboard_data/`

2. **Start a local server**:
   ```bash
   # Option 1: Python
   python -m http.server 8000
   
   # Option 2: Node.js
   npx serve .
   
   # Option 3: VS Code Live Server extension
   ```

3. **Open dashboard**:
   ```
   http://localhost:8000/
   ```
   
   Then navigate to dashboard with a UUID:
   ```  
   http://localhost:8000/dashboard?uuid={your-uuid}
   ```

## Production Deployment

### Option 1: Static Hosting (Netlify/Vercel)
1. Upload your JSON file to S3
2. Configure the S3 URL in `dashboard.js`:
   ```javascript
   // In getProductionDataUrl() method
   return 'https://your-bucket.s3.amazonaws.com/books.json';
   ```
3. Deploy the `dashboard/` folder to Netlify/Vercel

### Option 2: S3 Static Website
1. Upload dashboard files to S3
2. Enable static website hosting
3. Set CORS policy for JSON access

## File Structure

```
dashboard/
├── index.html          # Upload/landing page
├── dashboard.html      # Main analytics dashboard
├── books.html          # Filtered book listings
├── detail.html         # Individual book details
├── dashboard.js        # Dashboard logic and charts
├── books.js           # Book listing logic
├── detail.js          # Book detail logic
├── upload.js          # Upload handling
└── README.md          # This file

dashboard_data/
└── {uuid}.json        # Generated book data
```

## Customization

### Colors & Styling
- Edit Tailwind classes in `index.html`
- Modify chart colors in `dashboard.js`
- Add custom CSS in the `<style>` section

### Charts
- Uses Chart.js for all visualizations
- Easy to add new chart types
- Responsive and theme-aware

### Data Sources
- **Local**: Loads JSON files from `dashboard_data/` directory
- **Production**: S3-based JSON files via CloudFront
- **Environment Detection**: Automatic local vs production mode
- **Fallback**: Graceful error handling

## Chart Types

1. **📈 Books by Year**: Line chart showing reading trends
2. **🍩 Rating Distribution**: Doughnut chart of your ratings
3. **📊 Top Genres**: Horizontal bar chart of most-read genres
4. **📖 Pages Timeline**: Bar chart of pages read per year
5. **📚 Recent Books**: Table of your latest reads

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- No IE support (uses modern JavaScript features)
- Mobile responsive design

## Performance

- **Small bundle size**: No framework dependencies
- **Fast loading**: CDN resources only
- **Efficient rendering**: Canvas-based charts
- **Lazy loading**: Charts render only when needed

Perfect for showcasing your reading habits with a modern, professional look! 🚀