class ReadingDashboard {
    constructor() {
        this.data = null;
        this.charts = {};
        this.isDarkMode = localStorage.getItem('darkMode') === 'true';
        this.env = ENV;
        this.uuid = getUuidFromUrl();
    }

    async init() {
        this.setupDarkMode();
        this.setupEventListeners();
        this.data = await loadDataForUuid(this.uuid);
        
        if (this.data) {
            this.renderDashboard();
        } else {
            this.showError();
        }
    }

    setupDarkMode() {
        // Always enable dark mode since we only support dark theme
        const html = document.documentElement;
        html.classList.add('dark');
        this.isDarkMode = true;
    }

    setupEventListeners() {
        // Delete data functionality
        const deleteButton = document.getElementById('deleteDataButton');
        const deleteModal = document.getElementById('deleteModal');
        const cancelDelete = document.getElementById('cancelDelete');
        const confirmDelete = document.getElementById('confirmDelete');

        // Hide delete button for default/example UUID
        const defaultUuid = '759f8950-6946-4101-9c16-2aafc54d672d';
        if (this.uuid === defaultUuid) {
            deleteButton?.style.setProperty('display', 'none');
        }

        deleteButton?.addEventListener('click', () => {
            this.showDeleteModal();
        });

        cancelDelete?.addEventListener('click', () => {
            this.hideDeleteModal();
        });

        confirmDelete?.addEventListener('click', () => {
            this.deleteData();
        });

        // Close modal on background click
        deleteModal?.addEventListener('click', (e) => {
            if (e.target === deleteModal) {
                this.hideDeleteModal();
            }
        });

        // Share functionality
        const shareButton = document.getElementById('shareButton');
        shareButton?.addEventListener('click', () => {
            this.shareUrl();
        });
    }

    async loadData() {
        try {
            // Get UUID from URL path
            const uuid = this.getUuidFromUrl();
            
            if (!uuid) {
                throw new Error('No UUID provided in URL. Expected format: /dashboard/uuid or ?uuid=...');
            }

            // Always use API for both local-docker and cloud modes
            await this.loadDataFromAPI(uuid);
            
        } catch (error) {
            console.error('Error loading data:', error);
            this.data = null;
        }
    }

    // Removed local file loading - only API mode supported

    async loadDataFromAPI(uuid) {
        console.log(`Loading data from API: ${this.env.apiBase}/data/${uuid}`);
        
        const response = await fetch(`${this.env.apiBase}/data/${uuid}`);
        
        if (response.status === 202) {
            // Still processing
            this.showProcessingMessage();
            return;
        }
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Data not found. Please check the UUID or wait for processing to complete.');
            }
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        this.data = await response.json();
        console.log('Data loaded successfully from API');
    }

    showProcessingMessage() {
        const container = document.getElementById('dashboard-container');
        container.innerHTML = `
            <div class="text-center py-12">
                <div class="text-6xl mb-4">⏳</div>
                <h2 class="text-2xl font-bold text-gray-700 dark:text-gray-300 mb-4">Still Processing</h2>
                <p class="text-gray-600 dark:text-gray-400 mb-6">Your data is still being processed. This usually takes 5-10 minutes.</p>
                <button onclick="location.reload()" 
                        class="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
                    Refresh Page
                </button>
            </div>
        `;
    }

    getUuidFromUrl() {
        // Method 1: Check URL path (e.g., /dashboard/uuid or /uuid)
        const pathParts = window.location.pathname.split('/').filter(part => part);
        const lastPart = pathParts[pathParts.length - 1];
        
        // UUID regex pattern
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        
        if (uuidRegex.test(lastPart)) {
            return lastPart;
        }
        
        // Method 2: Check URL parameters (e.g., ?uuid=...)
        const urlParams = new URLSearchParams(window.location.search);
        const uuidParam = urlParams.get('uuid');
        
        if (uuidParam && uuidRegex.test(uuidParam)) {
            return uuidParam;
        }
        
        // Method 3: Check hash (e.g., #uuid)
        const hash = window.location.hash.substring(1);
        if (uuidRegex.test(hash)) {
            return hash;
        }
        
        return null;
    }

    // These methods are replaced by the new environment-aware loading

    renderDashboard() {
        this.hideLoading();
        this.showDashboard();
        
        this.updateSummaryCards();
        this.renderCharts();
        this.renderRecentBooks();
    }

    hideLoading() {
        document.getElementById('loading').classList.add('hidden');
    }

    showDashboard() {
        document.getElementById('dashboard').classList.remove('hidden');
    }

    showError() {
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('error').classList.remove('hidden');
    }

    updateSummaryCards() {
        const summary = this.data.summary;
        
        document.getElementById('totalBooks').textContent = summary.total_books || 0;
        document.getElementById('totalPages').textContent = (summary.total_pages || 0).toLocaleString();
        document.getElementById('avgRating').textContent = summary.average_rating ? 
            summary.average_rating.toFixed(1) : 'N/A';
        document.getElementById('readingYears').textContent = summary.reading_years ? 
            summary.reading_years.length : 0;

        // Update subtitle
        document.getElementById('subtitle').textContent = 
            `Your reading journey from ${summary.reading_date_range?.earliest || 'the beginning'} to ${summary.reading_date_range?.latest || 'now'}`;
    }

    renderCharts() {
        this.renderBooksByYearChart();
        this.renderRatingChart();
        this.renderGenresChart();
        this.renderPagesChart();
    }

    renderBooksByYearChart() {
        const books = this.data.books.filter(book => book.reading_year);
        const yearCounts = {};
        
        books.forEach(book => {
            yearCounts[book.reading_year] = (yearCounts[book.reading_year] || 0) + 1;
        });

        const years = Object.keys(yearCounts).sort();
        const counts = years.map(year => yearCounts[year]);

        const ctx = document.getElementById('booksByYearChart').getContext('2d');
        this.charts.booksByYear = new Chart(ctx, {
            type: 'line',
            data: {
                labels: years,
                datasets: [{
                    label: 'Books Read',
                    data: counts,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: this.getChartOptions()
        });
    }

    renderRatingChart() {
        const ratedBooks = this.data.books.filter(book => book.my_rating);
        const ratingCounts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
        
        ratedBooks.forEach(book => {
            ratingCounts[book.my_rating]++;
        });

        const chartData = Object.entries(ratingCounts).sort((a, b) => a[0] - b[0]);

        const ctx = document.getElementById('ratingChart').getContext('2d');
        this.charts.rating = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.map(d => `⭐`.repeat(d[0])),
                datasets: [{
                    label: 'Number of Books',
                    data: chartData.map(d => d[1]),
                    backgroundColor: [
                        '#ef4444',
                        '#f97316',
                        '#eab308',
                        '#22c55e',
                        '#16a34a'
                    ]
                }]
            },
            options: {
                ...this.getChartOptions(),
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const chartElement = elements[0];
                        const index = chartElement.index;
                        const rating = chartData[index][0];
                        const uuid = this.getUuidFromUrl();
                        window.location.href = `books?uuid=${uuid}&type=rating&value=${rating}`;
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    renderGenresChart() {
        const topGenres = this.data.summary.most_common_genres || [];
        const top10 = topGenres.slice(0, 10);

        const ctx = document.getElementById('genresChart').getContext('2d');
        this.charts.genres = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: top10.map(g => this.truncateText(g.genre, 20)),
                datasets: [{
                    label: 'Books',
                    data: top10.map(g => g.count),
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: '#667eea',
                    borderWidth: 1
                }]
            },
            options: {
                ...this.getChartOptions(),
                indexAxis: 'y',
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const chartElement = elements[0];
                        const index = chartElement.index;
                        const genre = top10[index].genre;
                        const uuid = this.getUuidFromUrl();
                        window.location.href = `books?uuid=${uuid}&type=genre&value=${encodeURIComponent(genre)}`;
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            color: this.isDarkMode ? 'rgba(75, 85, 99, 0.3)' : 'rgba(209, 213, 219, 0.3)'
                        },
                        ticks: {
                            color: this.isDarkMode ? '#d1d5db' : '#374151'
                        }
                    },
                    y: {
                        grid: {
                            color: this.isDarkMode ? 'rgba(75, 85, 99, 0.3)' : 'rgba(209, 213, 219, 0.3)'
                        },
                        ticks: {
                            color: this.isDarkMode ? '#d1d5db' : '#374151'
                        }
                    }
                }
            }
        });
    }

    renderPagesChart() {
        const books = this.data.books.filter(book => book.reading_year && book.num_pages);
        const yearPages = {};
        
        books.forEach(book => {
            yearPages[book.reading_year] = (yearPages[book.reading_year] || 0) + book.num_pages;
        });

        const years = Object.keys(yearPages).sort();
        const pages = years.map(year => yearPages[year]);

        const ctx = document.getElementById('pagesChart').getContext('2d');
        this.charts.pages = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: years,
                datasets: [{
                    label: 'Pages Read',
                    data: pages,
                    backgroundColor: 'rgba(34, 197, 94, 0.8)',
                    borderColor: '#22c55e',
                    borderWidth: 1
                }]
            },
            options: {
                ...this.getChartOptions(),
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const chartElement = elements[0];
                        const index = chartElement.index;
                        const year = years[index];
                        const uuid = this.getUuidFromUrl();
                        window.location.href = `books?uuid=${uuid}&type=pages-year&value=${year}`;
                    }
                }
            }
        });
    }

    renderRecentBooks() {
        const recentBooks = this.data.books
            .filter(book => book.date_read)
            .sort((a, b) => new Date(b.date_read) - new Date(a.date_read))
            .slice(0, 10);

        const tbody = document.getElementById('recentBooksTable');
        tbody.innerHTML = '';

        recentBooks.forEach(book => {
            const row = document.createElement('tr');
            row.className = 'border-b border-gray-700 hover:bg-gray-800';
            
            row.innerHTML = `
                <td class="py-3 px-4 text-white font-medium">
                    ${this.truncateText(book.title, 40)}
                </td>
                <td class="py-3 px-4 text-gray-300">
                    ${this.truncateText(book.author, 25)}
                </td>
                <td class="py-3 px-4 text-gray-300">
                    ${this.formatDate(book.date_read)}
                </td>
                <td class="py-3 px-4">
                    ${book.my_rating ? '⭐'.repeat(book.my_rating) : '-'}
                </td>
                <td class="py-3 px-4 text-gray-300">
                    ${book.num_pages ? book.num_pages.toLocaleString() : '-'}
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }

    getChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            onHover: (event, elements) => {
                // Change cursor to pointer when hovering over clickable chart elements
                event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#d1d5db'
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(75, 85, 99, 0.3)'
                    },
                    ticks: {
                        color: '#d1d5db'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(75, 85, 99, 0.3)'
                    },
                    ticks: {
                        color: '#d1d5db'
                    }
                }
            }
        };
    }

    updateChartsForTheme() {
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.options) {
                chart.options = { ...chart.options, ...this.getChartOptions() };
                chart.update();
            }
        });
    }

    truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    showDeleteModal() {
        const modal = document.getElementById('deleteModal');
        modal?.classList.remove('hidden');
    }

    hideDeleteModal() {
        const modal = document.getElementById('deleteModal');
        modal?.classList.add('hidden');
    }

    async deleteData() {
        const uuid = this.getUuidFromUrl();
        if (!uuid) {
            this.showDeleteError('No UUID found');
            return;
        }

        try {
            // Show loading state on confirm button
            const confirmButton = document.getElementById('confirmDelete');
            confirmButton.textContent = 'Deleting...';
            confirmButton.disabled = true;

            // Make DELETE request
            const response = await fetch(`${this.env.apiBase}/data/${uuid}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Delete successful:', result);
                
                // Hide modal and show success message
                this.hideDeleteModal();
                this.showDeleteSuccess();
                
                // Redirect to upload page after a short delay
                setTimeout(() => {
                    window.location.href = '../';
                }, 2000);
            } else {
                const errorData = await response.json().catch(() => ({ message: 'Delete failed' }));
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

        } catch (error) {
            console.error('Delete failed:', error);
            this.showDeleteError(error.message);
            
            // Reset button state
            const confirmButton = document.getElementById('confirmDelete');
            confirmButton.textContent = 'Delete Forever';
            confirmButton.disabled = false;
        }
    }

    shareUrl() {
        const currentUrl = window.location.href;
        
        // Try to use the modern clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(currentUrl).then(() => {
                this.showShareSuccess();
            }).catch(() => {
                this.fallbackCopyToClipboard(currentUrl);
            });
        } else {
            this.fallbackCopyToClipboard(currentUrl);
        }
    }

    fallbackCopyToClipboard(text) {
        // Fallback for older browsers or non-secure contexts
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            this.showShareSuccess();
        } catch (err) {
            console.error('Fallback copy failed:', err);
            this.showShareError();
        }
        document.body.removeChild(textArea);
    }

    showShareSuccess() {
        const button = document.getElementById('shareButton');
        const originalText = button.textContent;
        button.textContent = '✅ Copied!';
        button.classList.add('bg-green-500');
        button.classList.remove('bg-blue-500');
        
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('bg-green-500');
            button.classList.add('bg-blue-500');
        }, 2000);
    }

    showShareError() {
        const button = document.getElementById('shareButton');
        const originalText = button.textContent;
        button.textContent = '❌ Failed';
        button.classList.add('bg-red-500');
        button.classList.remove('bg-blue-500');
        
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('bg-red-500');
            button.classList.add('bg-blue-500');
        }, 2000);
    }

    showDeleteSuccess() {
        // Replace dashboard content with success message
        const dashboardContainer = document.getElementById('dashboard');
        dashboardContainer.innerHTML = `
            <div class="text-center py-20">
                <div class="text-6xl mb-4">✅</div>
                <h2 class="text-2xl font-bold text-gray-700 dark:text-gray-300 mb-4">Data Deleted Successfully</h2>
                <p class="text-gray-600 dark:text-gray-400 mb-6">Your reading data has been permanently removed.</p>
                <p class="text-gray-500 dark:text-gray-500">Redirecting to upload page...</p>
            </div>
        `;
    }

    showDeleteError(message) {
        // Show error in modal or as notification
        this.hideDeleteModal();
        
        // Create temporary error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50';
        errorDiv.innerHTML = `
            <div class="flex items-center">
                <span class="mr-2">❌</span>
                <span>Delete failed: ${message}</span>
            </div>
        `;
        
        document.body.appendChild(errorDiv);
        
        // Remove after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new ReadingDashboard();
    dashboard.init();
    
    // Handle View All Books button
    const viewAllBooksBtn = document.getElementById('viewAllBooksBtn');
    if (viewAllBooksBtn) {
        viewAllBooksBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const uuid = getUuidFromUrl();
            if (uuid) {
                window.location.href = `books?uuid=${uuid}&type=all&value=all`;
            }
        });
    }
});