class CSVUploader {
    constructor() {
        this.env = this.detectEnvironment();
        console.log('Environment detected:', this.env);
        this.setupElements();
        this.setupEventListeners();
    }

    detectEnvironment() {
        const host = window.location.host;
        
        if (host === 'localhost:8000' || host === '127.0.0.1:8000') {
            return {
                mode: 'local-docker',
                apiBase: 'http://localhost:8001'
            };
        } else if (host.includes('dev.goodreads-stats.codebycarson.com')) {
            return {
                mode: 'development',
                apiBase: 'https://dev.goodreads-stats.codebycarson.com/api'
            };
        } else if (host.includes('goodreads-stats.codebycarson.com')) {
            return {
                mode: 'production',
                apiBase: 'https://goodreads-stats.codebycarson.com/api'
            };
        } else {
            return {
                mode: 'cloud',
                apiBase: 'https://api.codebycarson.com/goodreads-stats'
            };
        }
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
            // Always use API for both local-docker and cloud modes
            await this.processViaAPI(file);
        } catch (error) {
            console.error('Processing error:', error);
            this.showError(`Failed to process your file: ${error.message}`);
            this.showUpload();
        }
    }

    // Removed local simple mode instructions

    async processViaAPI(file) {
        // Upload file to API
        this.updateProgress(10, 'Uploading file...');
        
        const formData = new FormData();
        formData.append('csv', file);
        
        const uploadResponse = await fetch(`${this.env.apiBase}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!uploadResponse.ok) {
            const errorData = await uploadResponse.json().catch(() => ({ error: 'Upload failed' }));
            throw new Error(errorData.error || errorData.detail || 'Upload failed');
        }
        
        const uploadResult = await uploadResponse.json();
        const uuid = uploadResult.job_id || uploadResult.uuid;
        console.log('Upload successful, Job ID:', uuid, 'Status:', uploadResult.status);
        
        // Poll for completion
        await this.pollForCompletion(uuid);
        
        // Redirect to dashboard
        this.updateProgress(100, 'Complete!');
        setTimeout(() => {
            window.location.href = `dashboard?uuid=${uuid}`;
        }, 1000);
    }

    async pollForCompletion(uuid) {
        const maxAttempts = 120; // 10 minutes max
        let attempts = 0;
        
        while (attempts < maxAttempts) {
            try {
                // Check if processing is complete by trying to get the data
                const dataResponse = await fetch(`${this.env.apiBase}/data/${uuid}`);
                
                if (dataResponse.ok) {
                    // Data is available - processing complete!
                    this.updateProgress(95, 'Processing complete!');
                    return;
                } else if (dataResponse.status === 404) {
                    // Data not ready yet - continue polling
                    const waitTime = Math.min(attempts * 500 + 2000, 10000); // 2-10 second intervals
                    const message = attempts < 5 ? 'Processing your books...' : 
                                   attempts < 20 ? 'Still processing (this may take a few minutes)...' :
                                   'Processing is taking longer than usual, but still working...';
                    
                    this.updateProgress(20 + Math.min(attempts * 2, 70), message);
                    
                    await new Promise(resolve => setTimeout(resolve, waitTime));
                    attempts++;
                    continue;
                } else {
                    throw new Error(`Processing check failed: ${dataResponse.status}`);
                }
                
            } catch (error) {
                console.error('Processing check error:', error);
                attempts++;
                
                if (attempts >= maxAttempts) {
                    throw new Error('Processing timed out. Please try again.');
                }
                
                // Wait before retry
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }
        
        throw new Error('Processing timed out. Please try again.');
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

    // These methods are no longer needed as we use the API
    // Keeping them for backwards compatibility with local-simple mode

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