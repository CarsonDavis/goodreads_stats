class BookDetailPage {
    constructor() {
        this.data = null;
        this.bookId = null;
        this.uuid = null;
        this.returnUrl = null;
        this.env = ENV; // Use the global ENV from utils.js
        this.init();
    }

    async init() {
        this.getUrlParams();
        this.data = await loadDataForUuid(this.uuid); // Use shared loadDataForUuid
        if (this.data && this.bookId) {
            this.renderBookDetails();
        } else {
            this.showError('Could not load book details.');
        }
    }

    getUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        this.bookId = urlParams.get('id'); // goodreads_id
        this.uuid = getUuidFromUrl(); // Use shared getUuidFromUrl
        this.returnUrl = urlParams.get('return') || 'dashboard';
        
        console.log(`Book params: id=${this.bookId}, uuid=${this.uuid}, return=${this.returnUrl}`);
    }

    renderBookDetails() {
        const book = this.data.books.find(b => b.goodreads_id === this.bookId);
        
        if (!book) {
            this.showError(`Book with ID ${this.bookId} not found.`);
            return;
        }

        this.updateHeader(book);
        this.updateBackButton();
        this.hideLoading();

        const detailsContainer = document.getElementById('book-details');
        detailsContainer.innerHTML = this.createBookDetailsHTML(book);
    }

    updateHeader(book) {
        document.getElementById('book-title').textContent = book.title;
        document.getElementById('book-author').textContent = `by ${book.author}`;
    }

    updateBackButton() {
        const backButton = document.getElementById('back-button');
        if (this.uuid) {
            // Preserve return URL with UUID
            if (this.returnUrl.includes('?')) {
                backButton.href = `${this.returnUrl}&uuid=${this.uuid}`;
            } else {
                backButton.href = `${this.returnUrl}?uuid=${this.uuid}`;
            }
        } else {
            backButton.href = this.returnUrl;
        }
    }

    createBookDetailsHTML(book) {
        const readDate = book.date_read ? new Date(book.date_read).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        }) : 'Unknown date';

        const ratingStars = book.my_rating ? '⭐'.repeat(book.my_rating) : 'Not rated';
        const averageRating = book.average_rating ? `${book.average_rating.toFixed(2)}/5` : 'No average rating';

        const genres = book.genres && book.genres.length > 0 
            ? book.genres.map(genre => `<a href="books.html?uuid=${this.uuid}&type=genre&value=${encodeURIComponent(genre)}" class="bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 px-2 py-1 rounded-full text-sm hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors cursor-pointer inline-block">${this.escapeHtml(genre)}</a>`).join(' ')
            : '<span class="text-gray-500">No genres</span>';

        const thumbnailSection = book.thumbnail_url ? `
            <div class="md:w-1/3">
                <img src="${book.thumbnail_url}" alt="Book cover" class="w-full max-w-sm mx-auto rounded-lg shadow-md">
            </div>
        ` : '';

        const reviewSection = book.has_review && book.my_review ? `
            <div class="mt-8">
                <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">My Review</h3>
                ${book.has_spoilers ? '<div class="bg-yellow-100 dark:bg-yellow-900 border border-yellow-400 text-yellow-700 dark:text-yellow-200 px-4 py-3 rounded mb-4"><strong>⚠️ Contains Spoilers</strong></div>' : ''}
                <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                    <div class="text-gray-800 dark:text-gray-200 prose dark:prose-invert max-w-none">${this.formatReviewHtml(book.my_review)}</div>
                </div>
            </div>
        ` : '';

        const notesSection = book.private_notes ? `
            <div class="mt-6">
                <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">Private Notes</h3>
                <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                    <p class="text-gray-800 dark:text-gray-200 whitespace-pre-wrap">${this.escapeHtml(book.private_notes)}</p>
                </div>
            </div>
        ` : '';

        return `
            <div class="md:flex gap-8 p-8">
                ${thumbnailSection}
                <div class="md:w-2/3">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Reading Info</h3>
                            <div class="space-y-2 text-sm">
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">My Rating:</span>
                                    <span class="text-yellow-500">${ratingStars}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">Average Rating:</span>
                                    <span class="text-gray-800 dark:text-gray-200">${averageRating}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">Date Read:</span>
                                    <span class="text-gray-800 dark:text-gray-200">${readDate}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">Pages:</span>
                                    <span class="text-gray-800 dark:text-gray-200">${book.num_pages || 'Unknown'}</span>
                                </div>
                                ${book.was_reread ? '<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Re-read:</span><span class="text-green-600 dark:text-green-400">Yes</span></div>' : ''}
                            </div>
                        </div>

                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Publication Info</h3>
                            <div class="space-y-2 text-sm">
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">Publisher:</span>
                                    <span class="text-gray-800 dark:text-gray-200">${book.publisher || 'Unknown'}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">Published:</span>
                                    <span class="text-gray-800 dark:text-gray-200">${book.publication_year || 'Unknown'}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">Binding:</span>
                                    <span class="text-gray-800 dark:text-gray-200">${book.binding || 'Unknown'}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-600 dark:text-gray-400">ISBN:</span>
                                    <span class="text-gray-800 dark:text-gray-200 font-mono text-xs">${book.isbn13 || book.isbn || 'None'}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="mb-6">
                        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Genres</h3>
                        <div class="flex flex-wrap gap-2">
                            ${genres}
                        </div>
                    </div>

                    ${book.bookshelves && book.bookshelves.length > 0 ? `
                        <div class="mb-6">
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Bookshelves</h3>
                            <div class="flex flex-wrap gap-2">
                                ${book.bookshelves.map(shelf => `<span class="bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 px-2 py-1 rounded-full text-sm">${this.escapeHtml(shelf)}</span>`).join(' ')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>

            ${reviewSection}
            ${notesSection}

            ${book.goodreads_id ? `
                <div class="p-6 border-t border-gray-200 dark:border-gray-700">
                    <a href="https://www.goodreads.com/book/show/${book.goodreads_id}" 
                       target="_blank" 
                       class="inline-flex items-center text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300">
                        View on Goodreads →
                    </a>
                </div>
            ` : ''}
        `;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatReviewHtml(reviewText) {
        if (!reviewText) return '';
        
        // First escape any potentially dangerous HTML, but preserve basic formatting tags
        let formatted = reviewText
            // Convert <br/> and <br> tags to line breaks
            .replace(/<br\s*\/?>/gi, '\n')
            // Convert <i> tags to italic
            .replace(/<i>(.*?)<\/i>/gi, '<em>$1</em>')
            // Convert <b> tags to bold
            .replace(/<b>(.*?)<\/b>/gi, '<strong>$1</strong>')
            // Handle blockquotes
            .replace(/<blockquote>(.*?)<\/blockquote>/gi, '<blockquote class="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic my-4">$1</blockquote>')
            // Remove any other HTML tags for security
            .replace(/<(?!\/?(em|strong|blockquote|p)\b)[^>]*>/gi, '');
        
        // Convert line breaks to paragraphs for better formatting
        const paragraphs = formatted.split('\n\n').filter(p => p.trim());
        if (paragraphs.length > 1) {
            return paragraphs.map(p => `<p class="mb-4">${p.trim()}</p>`).join('');
        } else {
            // Single paragraph or line-break separated text
            return formatted.replace(/\n/g, '<br>');
        }
    }

    hideLoading() {
        const loading = document.getElementById('loading');
        loading.style.display = 'none';
    }

    showError(message) {
        document.getElementById('book-title').textContent = 'Error';
        document.getElementById('book-author').textContent = '';
        const detailsContainer = document.getElementById('book-details');
        detailsContainer.innerHTML = `<div class="p-8 text-center"><p class="text-red-500">${message}</p></div>`;
        this.hideLoading();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new BookDetailPage();
});