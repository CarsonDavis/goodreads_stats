class CSVUploader {
    constructor() {
        this.setupElements();
        this.setupEventListeners();
    }

    setupElements() {
        this.uploadArea = document.getElementById('upload-area');
        this.fileInput = document.getElementById('file-input');
        this.uploadContent = document.getElementById('upload-content');
        this.processingContent = document.getElementById('processing-content');
        this.progressBar = document.getElementById('progress-bar');
        this.progressText = document.getElementById('progress-text');
        this.errorDisplay = document.getElementById('error-display');
        this.errorMessage = document.getElementById('error-message');
    }

    setupEventListeners() {
        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFile(e.target.files[0]);
            }
        });

        // Upload area click
        this.uploadArea.addEventListener('click', () => {
            this.fileInput.click();
        });

        // Drag and drop
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('dragover');
        });

        this.uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
        });

        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFile(files[0]);
            }
        });
    }

    async handleFile(file) {
        // Validate file
        if (!this.validateFile(file)) {
            return;
        }

        this.hideError();
        this.showProcessing();

        try {
            // Read and process the CSV file
            const csvText = await this.readFile(file);
            this.updateProgress(25, 'Parsing CSV data...');
            
            const books = this.parseCSV(csvText);
            this.updateProgress(50, 'Enriching book data...');
            
            const enrichedData = await this.enrichBooks(books);
            this.updateProgress(75, 'Generating dashboard...');
            
            const dashboardData = this.createDashboardData(enrichedData);
            this.updateProgress(90, 'Saving results...');
            
            const uuid = this.generateUUID();
            await this.saveDashboardData(uuid, dashboardData);
            
            this.updateProgress(100, 'Complete!');
            
            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = `dashboard/?uuid=${uuid}`;
            }, 1000);

        } catch (error) {
            console.error('Processing error:', error);
            this.showError('Failed to process your file. Please check that it\'s a valid Goodreads CSV export.');
            this.showUpload();
        }
    }

    validateFile(file) {
        // Check if it's a CSV file
        if (!file.name.toLowerCase().endsWith('.csv')) {
            this.showError('Please upload a CSV file from your Goodreads export.');
            return false;
        }

        // Check file size (limit to ~50MB)
        if (file.size > 50 * 1024 * 1024) {
            this.showError('File is too large. Please make sure it\'s a standard Goodreads export.');
            return false;
        }

        return true;
    }

    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsText(file);
        });
    }

    parseCSV(csvText) {
        const lines = csvText.split('\n');
        if (lines.length < 2) {
            throw new Error('CSV file appears to be empty or invalid');
        }

        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const books = [];

        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            const values = this.parseCSVLine(line);
            if (values.length !== headers.length) continue;

            const book = {};
            headers.forEach((header, index) => {
                book[header] = values[index].replace(/"/g, '').trim();
            });

            // Skip if no title
            if (!book.Title) continue;

            books.push(book);
        }

        return books;
    }

    parseCSVLine(line) {
        const values = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                values.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        values.push(current);
        
        return values;
    }

    async enrichBooks(books) {
        // For now, return a simplified version
        // In a full implementation, this would call the Python pipeline
        return books.map(book => ({
            title: book.Title || '',
            author: book.Author || '',
            my_rating: parseInt(book['My Rating']) || 0,
            date_read: book['Date Read'] || '',
            num_pages: parseInt(book['Number of Pages']) || 0,
            publisher: book.Publisher || '',
            isbn: book.ISBN || book.ISBN13 || '',
            goodreads_id: book['Book Id'] || Math.random().toString(36).substr(2, 9),
            reading_year: book['Date Read'] ? new Date(book['Date Read']).getFullYear() : null,
            genres: book.Bookshelves ? book.Bookshelves.split(',').map(g => g.trim()) : []
        }));
    }

    createDashboardData(books) {
        const totalBooks = books.length;
        const totalPages = books.reduce((sum, book) => sum + (book.num_pages || 0), 0);
        const ratedBooks = books.filter(book => book.my_rating > 0);
        const avgRating = ratedBooks.length > 0 
            ? (ratedBooks.reduce((sum, book) => sum + book.my_rating, 0) / ratedBooks.length).toFixed(1)
            : 0;
        
        const genreSet = new Set();
        books.forEach(book => {
            if (book.genres) {
                book.genres.forEach(genre => genreSet.add(genre));
            }
        });

        const yearSet = new Set(books.map(book => book.reading_year).filter(year => year));

        return {
            metadata: {
                total_books: totalBooks,
                total_pages: totalPages,
                avg_rating: parseFloat(avgRating),
                unique_genres: genreSet.size,
                reading_years: yearSet.size,
                generated_at: new Date().toISOString()
            },
            books: books
        };
    }

    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    async saveDashboardData(uuid, data) {
        // Since this is a client-side app, we can't actually save to the server
        // Instead, we'll provide instructions to the user on how to process their file
        
        // For now, create a download link for the processed data
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        // Create download link
        const a = document.createElement('a');
        a.href = url;
        a.download = `${uuid}.json`;
        a.style.display = 'none';
        document.body.appendChild(a);
        
        // Show instructions instead of redirecting
        this.showInstructions(uuid, url);
        
        // Simulate processing time
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    showInstructions(uuid, downloadUrl) {
        // Replace the processing content with instructions
        this.processingContent.innerHTML = `
            <div class="text-center">
                <div class="text-5xl mb-4">📋</div>
                <h3 class="text-xl font-bold text-gray-700 mb-4">Processing Complete!</h3>
                <p class="text-gray-600 mb-6">Your dashboard data has been generated. To get the full experience with enriched genre data:</p>
                
                <div class="bg-gray-50 p-4 rounded-lg mb-6">
                    <h4 class="font-semibold mb-2">For Full Processing:</h4>
                    <ol class="text-sm text-gray-600 text-left space-y-1">
                        <li>1. Clone this repository</li>
                        <li>2. Place your CSV in the <code>data/</code> folder</li>
                        <li>3. Run <code>python run_smart_pipeline.py</code></li>
                        <li>4. Open the dashboard with your UUID</li>
                    </ol>
                </div>
                
                <div class="space-x-4">
                    <a href="${downloadUrl}" download="${uuid}.json" 
                       class="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
                        Download Basic Data
                    </a>
                    <button onclick="location.reload()" 
                            class="bg-gray-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-gray-700 transition-colors">
                        Upload Another File
                    </button>
                </div>
            </div>
        `;
    }

    showProcessing() {
        this.uploadContent.classList.add('hidden');
        this.processingContent.classList.remove('hidden');
    }

    showUpload() {
        this.uploadContent.classList.remove('hidden');
        this.processingContent.classList.add('hidden');
    }

    updateProgress(percent, text) {
        this.progressBar.style.width = `${percent}%`;
        this.progressText.textContent = text;
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorDisplay.classList.remove('hidden');
    }

    hideError() {
        this.errorDisplay.classList.add('hidden');
    }
}

// Initialize uploader when page loads
document.addEventListener('DOMContentLoaded', () => {
    new CSVUploader();
});