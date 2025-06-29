// Modern Reading Dashboard - Vanilla JS
class ReadingDashboard {
    constructor() {
        this.data = null;
        this.charts = {};
        this.isDarkMode = localStorage.getItem('darkMode') === 'true';
        
        this.init();
    }

    async init() {
        this.setupDarkMode();
        this.setupEventListeners();
        await this.loadData();
        
        if (this.data) {
            this.renderDashboard();
        } else {
            this.showError();
        }
    }

    setupDarkMode() {
        const html = document.documentElement;
        if (this.isDarkMode) {
            html.classList.add('dark');
        }
        
        document.getElementById('darkModeToggle').addEventListener('click', () => {
            this.isDarkMode = !this.isDarkMode;
            localStorage.setItem('darkMode', this.isDarkMode);
            html.classList.toggle('dark');
            
            // Update chart colors for dark mode
            this.updateChartsForTheme();
        });
    }

    setupEventListeners() {
        // Add any additional event listeners here
    }

    async loadData() {
        try {
            // Get UUID from URL path
            const uuid = this.getUuidFromUrl();
            
            if (!uuid) {
                throw new Error('No UUID provided in URL. Expected format: /dashboard/uuid or ?uuid=...');
            }

            // Check if we're in local development
            const isLocal = window.location.protocol === 'file:' || 
                           window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1';

            let dataUrl;
            
            if (isLocal) {
                // Local development - load specific UUID file
                dataUrl = this.getLocalDataUrl(uuid);
            } else {
                // Production - load from S3 with UUID
                dataUrl = this.getProductionDataUrl(uuid);
            }

            console.log('Loading data from:', dataUrl);
            
            const response = await fetch(dataUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.data = await response.json();
            console.log('Data loaded successfully:', this.data);
            
        } catch (error) {
            console.error('Error loading data:', error);
            this.data = null;
        }
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

    getLocalDataUrl(uuid) {
        // Local development - try multiple paths for UUID file
        const possiblePaths = [
            `../dashboard_data/${uuid}.json`,
            `./dashboard_data/${uuid}.json`, 
            `dashboard_data/${uuid}.json`,
            `../${uuid}.json`,
            `./${uuid}.json`,
            `${uuid}.json`
        ];
        
        // Return the first path for now - we'll try them in sequence if needed
        return possiblePaths[0];
    }

    getProductionDataUrl(uuid) {
        // Production - S3 bucket with UUID filename
        const baseUrl = window.S3_BASE_URL || 'https://your-bucket.s3.amazonaws.com';
        return `${baseUrl}/${uuid}.json`;
    }

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
        document.getElementById('uniqueGenres').textContent = summary.unique_genres || 0;
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

        const ctx = document.getElementById('ratingChart').getContext('2d');
        this.charts.rating = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['⭐', '⭐⭐', '⭐⭐⭐', '⭐⭐⭐⭐', '⭐⭐⭐⭐⭐'],
                datasets: [{
                    data: [ratingCounts[1], ratingCounts[2], ratingCounts[3], ratingCounts[4], ratingCounts[5]],
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
                plugins: {
                    legend: {
                        position: 'bottom'
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
            options: this.getChartOptions()
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
            row.className = 'border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800';
            
            row.innerHTML = `
                <td class="py-3 px-4 text-gray-900 dark:text-white font-medium">
                    ${this.truncateText(book.title, 40)}
                </td>
                <td class="py-3 px-4 text-gray-600 dark:text-gray-300">
                    ${this.truncateText(book.author, 25)}
                </td>
                <td class="py-3 px-4 text-gray-600 dark:text-gray-300">
                    ${this.formatDate(book.date_read)}
                </td>
                <td class="py-3 px-4">
                    ${book.my_rating ? '⭐'.repeat(book.my_rating) : '-'}
                </td>
                <td class="py-3 px-4 text-gray-600 dark:text-gray-300">
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
            plugins: {
                legend: {
                    labels: {
                        color: this.isDarkMode ? '#d1d5db' : '#374151'
                    }
                }
            },
            scales: {
                x: {
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
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ReadingDashboard();
});