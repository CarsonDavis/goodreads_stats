class BooksPage {
    constructor() {
        this.data = null;
        this.filterType = null;
        this.filterValue = null;
        this.uuid = null;
        this.init();
    }

    async init() {
        this.getUrlParams();
        await this.loadData();
        if (this.data && this.filterType && this.filterValue !== null) {
            this.renderPage();
        } else {
            this.showError('Could not load data or missing filter parameters.');
        }
    }

    getUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        this.filterType = urlParams.get('type'); // 'genre', 'rating', 'year'
        this.filterValue = urlParams.get('value');
        this.uuid = urlParams.get('uuid');
        
        console.log(`Filter params: type=${this.filterType}, value=${this.filterValue}, uuid=${this.uuid}`);
    }

    async loadData() {
        if (!this.uuid) {
            console.error('No UUID found in URL');
            return;
        }
        try {
            const dataUrl = `../dashboard_data/${this.uuid}.json`;
            console.log(`Attempting to load data from: ${dataUrl}`)
            const response = await fetch(dataUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            this.data = await response.json();
            console.log('Data loaded successfully');
        } catch (error) {
            console.error('Error loading data:', error);
            this.data = null;
        }
    }

    renderPage() {
        this.updatePageTitle();
        this.hideLoading();
        
        const bookList = document.getElementById('book-list');
        bookList.innerHTML = ''; // Clear previous content
        
        console.log(`Filtering for ${this.filterType}: "${this.filterValue}"`);

        const filteredBooks = this.filterBooks();
        console.log(`Found ${filteredBooks.length} books.`);

        if (filteredBooks.length === 0) {
            bookList.innerHTML = '<div class="col-span-full"><p class="text-gray-400 text-center py-8">No books found for this filter.</p></div>';
            this.logSampleData();
            return;
        }

        filteredBooks.forEach(book => {
            const card = this.createBookCard(book);
            bookList.appendChild(card);
        });
    }

    updatePageTitle() {
        const titleElement = document.getElementById('page-title');
        const subtitleElement = document.getElementById('page-subtitle');
        
        let title, subtitle;
        
        switch (this.filterType) {
            case 'genre':
                title = `Books in Genre: ${this.filterValue}`;
                subtitle = `All books tagged with "${this.filterValue}"`;
                break;
            case 'rating':
                const stars = '⭐'.repeat(parseInt(this.filterValue));
                title = `${stars} Rated Books`;
                subtitle = `All books you rated ${this.filterValue} stars`;
                break;
            case 'year':
                title = `Books Read in ${this.filterValue}`;
                subtitle = `All books you read during ${this.filterValue}`;
                break;
            case 'pages-year':
                title = `Pages Read in ${this.filterValue}`;
                subtitle = `All books contributing to pages read in ${this.filterValue}`;
                break;
            default:
                title = 'Filtered Books';
                subtitle = `Filter: ${this.filterType} = ${this.filterValue}`;
        }
        
        titleElement.textContent = title;
        subtitleElement.textContent = subtitle;
    }

    filterBooks() {
        switch (this.filterType) {
            case 'genre':
                return this.data.books.filter(book => 
                    book.genres && book.genres.map(g => g.trim()).includes(this.filterValue.trim())
                );
            case 'rating':
                const targetRating = parseInt(this.filterValue);
                return this.data.books.filter(book => book.my_rating === targetRating);
            case 'year':
            case 'pages-year':
                const targetYear = parseInt(this.filterValue);
                return this.data.books.filter(book => book.reading_year === targetYear);
            default:
                console.error(`Unknown filter type: ${this.filterType}`);
                return [];
        }
    }

    createBookCard(book) {
        const card = document.createElement('div');
        card.className = 'bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow';
        
        const ratingDisplay = book.my_rating ? '⭐'.repeat(book.my_rating) : 'Not Rated';
        const readDate = book.date_read ? new Date(book.date_read).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        }) : 'Unknown date';
        
        const pages = book.num_pages ? `${book.num_pages} pages` : 'Unknown length';
        const genres = book.genres && book.genres.length > 0 ? book.genres.slice(0, 3).join(', ') : 'No genres';
        
        let thumbnailHtml = '';
        if (book.thumbnail_url) {
            thumbnailHtml = `
                <div class="mb-4">
                    <img src="${book.thumbnail_url}" alt="Book cover" class="w-24 h-32 object-cover rounded shadow-sm mx-auto">
                </div>
            `;
        }
        
        card.innerHTML = `
            ${thumbnailHtml}
            <h2 class="text-xl font-bold text-gray-900 dark:text-white mb-2">${this.escapeHtml(book.title)}</h2>
            <p class="text-gray-600 dark:text-gray-400 mb-2">by ${this.escapeHtml(book.author)}</p>
            <div class="space-y-2 text-sm text-gray-500 dark:text-gray-400">
                <div class="flex justify-between">
                    <span>Rating:</span>
                    <span class="text-yellow-400">${ratingDisplay}</span>
                </div>
                <div class="flex justify-between">
                    <span>Read:</span>
                    <span>${readDate}</span>
                </div>
                <div class="flex justify-between">
                    <span>Length:</span>
                    <span>${pages}</span>
                </div>
                <div class="mt-3">
                    <span class="text-xs text-gray-400">Genres:</span>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${genres}</p>
                </div>
            </div>
        `;
        
        return card;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    hideLoading() {
        const loading = document.getElementById('loading');
        loading.style.display = 'none';
    }

    logSampleData() {
        console.log("No match. Checking sample data:");
        console.log(`Filter type: ${this.filterType}, value: ${this.filterValue}`);
        
        this.data.books.slice(0, 3).forEach(book => {
            console.log(`- ${book.title}:`, {
                genres: book.genres,
                rating: book.my_rating,
                year: book.reading_year,
                pages: book.num_pages
            });
        });
    }

    showError(message) {
        document.getElementById('page-title').textContent = 'Error';
        document.getElementById('page-subtitle').textContent = '';
        const bookList = document.getElementById('book-list');
        bookList.innerHTML = `<div class="col-span-full"><p class="text-red-500 text-center py-8">${message}</p></div>`;
        this.hideLoading();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new BooksPage();
});