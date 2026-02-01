Chart.register(ChartDataLabels);

// Custom plugin to draw separator line
const separatorPlugin = {
    id: 'separatorLine',
    afterDraw: (chart) => {
        const options = chart.options.plugins.separatorLine;
        if (!options || options.separatorIndex === undefined || options.separatorIndex < 0) return;
        if (!chart.scales.y || !chart.scales.x) return;

        const ctx = chart.ctx;
        const yAxis = chart.scales.y;
        const xAxis = chart.scales.x;

        const yPos = yAxis.getPixelForValue(options.separatorIndex);

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(xAxis.left, yPos);
        ctx.lineTo(xAxis.right, yPos);
        ctx.lineWidth = 2;
        ctx.strokeStyle = 'rgba(107, 114, 128, 0.8)';
        ctx.stroke();
        ctx.restore();
    }
};

Chart.register(separatorPlugin);

class GenresPage {
    constructor() {
        this.data = null;
        this.uuid = null;
        this.env = ENV;
        this.chart = null;
        this.excludedGenres = ['Audiobook'];
        this.topGenres = ['Fiction', 'Nonfiction'];
        this.separatorIndex = -1;
        this.genreData = [];
        this.init();
    }

    async init() {
        this.uuid = getUuidFromUrl();
        this.updateBackButton();
        this.data = await loadDataForUuid(this.uuid);

        if (this.data) {
            this.renderPage();
        } else {
            this.showError('Could not load data. Please check the UUID.');
        }
    }

    updateBackButton() {
        const backButton = document.getElementById('back-to-dashboard');
        if (this.uuid) {
            backButton.href = `dashboard?uuid=${this.uuid}`;
        }
    }

    getAllGenreCounts() {
        const counts = {};
        this.data.books.forEach(book => {
            (book.genres || []).forEach(genre => {
                const trimmedGenre = genre.trim();
                counts[trimmedGenre] = (counts[trimmedGenre] || 0) + 1;
            });
        });

        return Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .map(([genre, count]) => ({ genre, count }));
    }

    buildChartData() {
        const allGenreCounts = this.getAllGenreCounts();

        // Get Fiction and Nonfiction
        const fictionCounts = allGenreCounts.filter(g => this.topGenres.includes(g.genre));

        // Get all other genres (excluding Fiction, Nonfiction, Audiobook)
        const otherGenreCounts = allGenreCounts.filter(g =>
            !this.topGenres.includes(g.genre) && !this.excludedGenres.includes(g.genre)
        );

        // Build combined data: Fiction/Nonfiction, then rest
        const combined = [];

        // Add Fiction/Nonfiction first
        fictionCounts.forEach(g => combined.push({ ...g, isTop: true }));

        // Remember where to draw the separator (after the last top genre)
        this.separatorIndex = combined.length - 0.5;

        // Add other genres
        otherGenreCounts.forEach(g => combined.push({ ...g, isTop: false }));

        this.genreData = combined;
        return combined;
    }

    renderPage() {
        this.hideLoading();

        const chartData = this.buildChartData();
        const otherCount = chartData.filter(g => !g.isTop).length;

        // Update subtitle with count
        document.getElementById('page-subtitle').textContent =
            `${otherCount} unique genres from your reading library`;

        this.renderChart(chartData);
    }

    renderChart(chartData) {
        // Calculate dynamic height based on number of items (25px per bar)
        const chartHeight = Math.max(400, chartData.length * 25);
        const container = document.getElementById('chart-container');
        container.style.height = `${chartHeight}px`;

        const ctx = document.getElementById('genresChart').getContext('2d');

        // Build colors array
        const colors = chartData.map(g => {
            if (g.genre === 'Fiction') return 'rgba(34, 197, 94, 0.8)';
            if (g.genre === 'Nonfiction') return 'rgba(168, 85, 247, 0.8)';
            return 'rgba(102, 126, 234, 0.8)';
        });

        const borderColors = chartData.map(g => {
            if (g.genre === 'Fiction') return '#22c55e';
            if (g.genre === 'Nonfiction') return '#a855f7';
            return '#667eea';
        });

        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.map(g => g.genre),
                datasets: [{
                    label: 'Books',
                    data: chartData.map(g => g.count),
                    backgroundColor: colors,
                    borderColor: borderColors,
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const item = this.genreData[index];
                        window.location.href = `books?uuid=${this.uuid}&type=genre&value=${encodeURIComponent(item.genre)}`;
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const count = context.raw;
                                return `${count} book${count !== 1 ? 's' : ''}`;
                            }
                        }
                    },
                    datalabels: {
                        anchor: 'end',
                        align: 'end',
                        color: '#d1d5db',
                        font: {
                            weight: 'bold',
                            size: 11
                        },
                        formatter: (value) => value
                    },
                    separatorLine: {
                        separatorIndex: this.separatorIndex
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
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
            }
        });
    }

    hideLoading() {
        const loading = document.getElementById('loading');
        loading.style.display = 'none';
    }

    showError(message) {
        const container = document.getElementById('chart-container');
        container.innerHTML = `<p class="text-red-500 text-center py-8">${message}</p>`;
        this.hideLoading();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new GenresPage();
});
