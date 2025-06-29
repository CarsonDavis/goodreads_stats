class GenrePage {
    constructor() {
        this.data = null;
        this.genre = null;
        this.uuid = null;
        this.init();
    }

    async init() {
        this.getUrlParams();
        await this.loadData();
        if (this.data && this.genre) {
            this.renderPage();
        } else {
            this.showError('Could not load data for this genre.');
        }
    }

    getUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        this.genre = decodeURIComponent(urlParams.get('genre'));
        this.uuid = urlParams.get('uuid');
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
        document.getElementById('genre-title').textContent = `Books in Genre: ${this.genre}`;
        const bookList = document.getElementById('book-list');
        bookList.innerHTML = ''; // Clear previous content
        
        console.log(`Filtering for genre: "${this.genre}"`);

        const filteredBooks = this.data.books.filter(book => 
            book.genres && book.genres.map(g => g.trim()).includes(this.genre.trim())
        );

        console.log(`Found ${filteredBooks.length} books.`);

        if (filteredBooks.length === 0) {
            bookList.innerHTML = '<p class="text-gray-400">No books found in this genre.</p>';
            // Log first 5 book genres for debugging
            console.log("No match. Checking genres from first 5 books:");
            this.data.books.slice(0, 5).forEach(book => {
                console.log(`- ${book.title}:`, book.genres);
            });
            return;
        }

        filteredBooks.forEach(book => {
            const card = document.createElement('div');
            card.className = 'bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md';
            card.innerHTML = `
                <h2 class="text-xl font-bold text-gray-900 dark:text-white">${book.title}</h2>
                <p class="text-gray-600 dark:text-gray-400 mb-2">by ${book.author}</p>
                <div class="text-yellow-400">${book.my_rating ? '⭐'.repeat(book.my_rating) : 'Not Rated'}</div>
            `;
            bookList.appendChild(card);
        });
    }

    showError(message) {
        document.getElementById('genre-title').textContent = 'Error';
        const bookList = document.getElementById('book-list');
        bookList.innerHTML = `<p class="text-red-500">${message}</p>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new GenrePage();
});