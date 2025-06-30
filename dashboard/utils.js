const ENV = detectEnvironment();

function detectEnvironment() {
    const host = window.location.host;
    
    if (host === 'localhost:8000' || host === '127.0.0.1:8000') {
        return {
            mode: 'local-docker',
            apiBase: 'http://localhost:8001'
        };
    } else if (host === 'dev.goodreads-stats.codebycarson.com') {
        return {
            mode: 'development',
            apiBase: 'https://dev.goodreads-stats.codebycarson.com/api'
        };
    } else if (host === 'goodreads-stats.codebycarson.com') {
        return {
            mode: 'production',
            apiBase: 'https://goodreads-stats.codebycarson.com/api'
        };
    } else {
        // Fallback for local development without API
        return {
            mode: 'local-static',
            apiBase: null,
            dataPath: 'dashboard_data/'
        };
    }
}

function getUuidFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const uuidParam = urlParams.get('uuid');
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    
    if (uuidParam && uuidRegex.test(uuidParam)) {
        return uuidParam;
    }
    return null;
}

async function loadDataForUuid(uuid) {
    if (!uuid) {
        throw new Error('No UUID provided to loadDataForUuid');
    }
    try {
        const dataUrl = `${ENV.apiBase}/data/${uuid}`;
        console.log(`Attempting to load data from: ${dataUrl}`);
        const response = await fetch(dataUrl);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error loading data:', error);
        return null;
    }
}
