// Email Search Frontend Application

// Global state
let authHeader = null;
let currentSearchType = 'vector';
let currentPage = 1;
let currentToken = null;
let prevToken = null;
let hasMore = false;
let currentQuery = '';
let currentFilters = {};
let currentEmailId = null; // For thread modal

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    const savedAuth = sessionStorage.getItem('authHeader');
    if (savedAuth) {
        authHeader = savedAuth;
        showMainApp();
    }

    // Setup login form
    document.getElementById('loginForm').addEventListener('submit', handleLogin);

    // Setup search on Enter key
    document.getElementById('searchQuery').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Setup search type radio buttons
    document.querySelectorAll('input[name="searchType"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentSearchType = e.target.value;
        });
    });
});

// Authentication
async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    
    // Create Basic Auth header
    const credentials = btoa(`${username}:${password}`);
    const testAuthHeader = `Basic ${credentials}`;
    
    try {
        // Test authentication by calling tags endpoint
        const response = await fetch('/api/tags', {
            headers: {
                'Authorization': testAuthHeader
            }
        });
        
        if (response.ok) {
            authHeader = testAuthHeader;
            sessionStorage.setItem('authHeader', authHeader);
            errorDiv.textContent = '';
            showMainApp();
        } else {
            errorDiv.textContent = 'Invalid username or password';
        }
    } catch (error) {
        errorDiv.textContent = 'Connection error. Please try again.';
    }
}

function logout() {
    authHeader = null;
    sessionStorage.removeItem('authHeader');
    document.getElementById('loginContainer').classList.remove('hidden');
    document.getElementById('mainApp').classList.add('hidden');
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
}

async function showMainApp() {
    document.getElementById('loginContainer').classList.add('hidden');
    document.getElementById('mainApp').classList.remove('hidden');
    
    // Load tags
    await loadTags();
}

// Load tags/mailboxes
async function loadTags() {
    try {
        const response = await fetch('/api/tags', {
            headers: { 'Authorization': authHeader }
        });
        
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('tagFilter');
            
            // Clear existing options except "All Tags"
            select.innerHTML = '<option value="">All Tags</option>';
            
            // Add tags
            data.tags.forEach(tag => {
                const option = document.createElement('option');
                option.value = tag;
                option.textContent = tag;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading tags:', error);
    }
}

// Search functionality
async function performSearch(token = null, direction = 'after') {
    const query = document.getElementById('searchQuery').value.trim();
    
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    // Get search type
    const searchType = document.querySelector('input[name="searchType"]:checked').value;
    
    // Get filters
    const tag = document.getElementById('tagFilter').value;
    const dateStart = document.getElementById('dateStart').value;
    const dateEnd = document.getElementById('dateEnd').value;
    
    // Build query parameters
    const params = new URLSearchParams({
        query: query,
        search_type: searchType,
        page_size: '25'
    });
    
    if (searchType === 'vector') {
        // Reset page if new search
        if (query !== currentQuery || tag !== currentFilters.tag || 
            dateStart !== currentFilters.dateStart || dateEnd !== currentFilters.dateEnd) {
            currentPage = 1;
        }
        params.append('page', currentPage.toString());
    } else {
        // Text search with tokens
        if (token) {
            params.append('token', token);
            params.append('direction', direction);
        }
    }
    
    if (tag) params.append('tag', tag);
    if (dateStart) params.append('date_start', dateStart + 'T00:00:00');
    if (dateEnd) params.append('date_end', dateEnd + 'T23:59:59');
    
    // Save current search state
    currentQuery = query;
    currentSearchType = searchType;
    currentFilters = { tag, dateStart, dateEnd };
    
    // Show loading
    showLoading();
    
    try {
        const response = await fetch(`/api/search?${params}`, {
            headers: { 'Authorization': authHeader }
        });
        
        if (response.ok) {
            const data = await response.json();
            displayResults(data);
        } else if (response.status === 401) {
            logout();
        } else {
            alert('Search failed. Please try again.');
            hideLoading();
        }
    } catch (error) {
        console.error('Search error:', error);
        alert('Connection error. Please try again.');
        hideLoading();
    }
}

function displayResults(data) {
    hideLoading();
    
    const resultsBody = document.getElementById('resultsBody');
    const resultsTable = document.getElementById('resultsTable');
    const noResults = document.getElementById('noResults');
    const resultsCount = document.getElementById('resultsCount');
    
    // Clear existing results
    resultsBody.innerHTML = '';
    
    if (data.results.length === 0) {
        resultsTable.classList.add('hidden');
        noResults.classList.remove('hidden');
        resultsCount.textContent = '';
        updatePagination(data.pagination);
        return;
    }
    
    resultsTable.classList.remove('hidden');
    noResults.classList.add('hidden');
    
    // Update results count
    resultsCount.textContent = `Showing ${data.results.length} results`;
    
    // Add results
    data.results.forEach(email => {
        const row = document.createElement('tr');
        
        const dateStr = email.date ? new Date(email.date).toLocaleString() : 'N/A';
        const snippet = email.bodySnippet || '';
        
        row.innerHTML = `
            <td><span class="email-subject" onclick="viewEmail('${email._id}')">${escapeHtml(email.subject || 'No Subject')}</span></td>
            <td>${escapeHtml(email.from || 'N/A')}</td>
            <td>${dateStr}</td>
            <td><span class="email-snippet">${escapeHtml(snippet)}</span></td>
            <td>${escapeHtml(email.tag || 'N/A')}</td>
            <td>
                <div class="email-actions">
                    <button class="btn-small" onclick="viewEmail('${email._id}')">View</button>
                    <button class="btn-small btn-thread" onclick="viewThread('${email._id}')">Thread</button>
                </div>
            </td>
        `;
        
        resultsBody.appendChild(row);
    });
    
    // Update pagination
    updatePagination(data.pagination);
}

function updatePagination(pagination) {
    hasMore = pagination.hasMore;
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    if (pagination.searchType === 'vector') {
        // Page-based pagination
        prevBtn.disabled = !pagination.prevPage;
        nextBtn.disabled = !pagination.nextPage;
        
        prevBtn.textContent = 'Previous';
        nextBtn.textContent = pagination.nextPage ? `Next (Page ${pagination.nextPage})` : 'Next';
    } else {
        // Token-based pagination
        currentToken = pagination.nextToken;
        prevToken = pagination.prevToken;
        
        prevBtn.disabled = !prevToken;
        nextBtn.disabled = !hasMore;
        
        prevBtn.textContent = 'Previous';
        nextBtn.textContent = 'Next';
    }
}

function previousPage() {
    if (currentSearchType === 'vector') {
        if (currentPage > 1) {
            currentPage--;
            performSearch();
        }
    } else {
        if (prevToken) {
            performSearch(prevToken, 'before');
        }
    }
}

function nextPage() {
    if (currentSearchType === 'vector') {
        if (hasMore && currentPage < 20) {
            currentPage++;
            performSearch();
        }
    } else {
        if (currentToken && hasMore) {
            performSearch(currentToken, 'after');
        }
    }
}

// Email detail modal
async function viewEmail(emailId) {
    const modal = document.getElementById('emailModal');
    const modalBody = document.getElementById('emailModalBody');
    
    modalBody.innerHTML = '<div class="loading">Loading email...</div>';
    modal.classList.add('active');
    
    try {
        const response = await fetch(`/api/emails/${emailId}`, {
            headers: { 'Authorization': authHeader }
        });
        
        if (response.ok) {
            const email = await response.json();
            displayEmailDetail(email);
        } else {
            modalBody.innerHTML = '<div class="error">Failed to load email.</div>';
        }
    } catch (error) {
        console.error('Error loading email:', error);
        modalBody.innerHTML = '<div class="error">Connection error.</div>';
    }
}

function displayEmailDetail(email) {
    const modalBody = document.getElementById('emailModalBody');
    const dateStr = email.date ? new Date(email.date).toLocaleString() : 'N/A';
    
    modalBody.innerHTML = `
        <div class="email-detail">
            <div class="email-field">
                <span class="email-field-label">Subject:</span>
                <span class="email-field-value">${escapeHtml(email.subject || 'No Subject')}</span>
            </div>
            <div class="email-field">
                <span class="email-field-label">From:</span>
                <span class="email-field-value">${escapeHtml(email.from || 'N/A')}</span>
            </div>
            <div class="email-field">
                <span class="email-field-label">To:</span>
                <span class="email-field-value">${escapeHtml(email.to || 'N/A')}</span>
            </div>
            <div class="email-field">
                <span class="email-field-label">Date:</span>
                <span class="email-field-value">${dateStr}</span>
            </div>
            <div class="email-field">
                <span class="email-field-label">Tag:</span>
                <span class="email-field-value">${escapeHtml(email.tag || 'N/A')}</span>
            </div>
            <div class="email-field">
                <span class="email-field-label">Body:</span>
            </div>
            <div class="email-body">${escapeHtml(email.body || 'No content')}</div>
        </div>
    `;
}

function closeEmailModal() {
    document.getElementById('emailModal').classList.remove('active');
}

// Thread modal
async function viewThread(emailId) {
    currentEmailId = emailId;
    const modal = document.getElementById('threadModal');
    const threadContent = document.getElementById('threadContent');
    const threadBanner = document.getElementById('threadBanner');
    
    threadContent.innerHTML = '<div class="loading">Loading thread...</div>';
    threadBanner.classList.add('hidden');
    modal.classList.add('active');
    
    const days = document.getElementById('threadDays').value;
    
    try {
        const response = await fetch(`/api/emails/${emailId}/thread?days=${days}`, {
            headers: { 'Authorization': authHeader }
        });
        
        if (response.ok) {
            const data = await response.json();
            displayThread(data);
        } else {
            threadContent.innerHTML = '<div class="error">Failed to load thread.</div>';
        }
    } catch (error) {
        console.error('Error loading thread:', error);
        threadContent.innerHTML = '<div class="error">Connection error.</div>';
    }
}

function displayThread(data) {
    const threadContent = document.getElementById('threadContent');
    const threadBanner = document.getElementById('threadBanner');
    
    // Show banner if there are additional emails outside window
    if (data.additionalCount > 0) {
        threadBanner.textContent = `${data.additionalCount} more email${data.additionalCount > 1 ? 's' : ''} in this thread outside the selected ${data.dateWindow}-day window`;
        threadBanner.classList.remove('hidden');
    } else {
        threadBanner.classList.add('hidden');
    }
    
    if (data.thread.length === 0) {
        threadContent.innerHTML = '<div class="no-results">No emails found in thread.</div>';
        return;
    }
    
    threadContent.innerHTML = '';
    
    data.thread.forEach((email, index) => {
        const emailDiv = document.createElement('div');
        emailDiv.className = 'thread-email';
        
        const dateStr = email.date ? new Date(email.date).toLocaleString() : 'N/A';
        const isBaseEmail = email._id === data.baseEmailId;
        
        emailDiv.innerHTML = `
            <div class="thread-email-header" onclick="toggleThreadEmail(${index})">
                <div class="thread-email-info">
                    <h4>${escapeHtml(email.subject || 'No Subject')}${isBaseEmail ? ' (Selected Email)' : ''}</h4>
                    <div class="thread-email-meta">
                        From: ${escapeHtml(email.from || 'N/A')} → To: ${escapeHtml(email.to || 'N/A')}
                    </div>
                </div>
                <div class="thread-email-date">${dateStr}</div>
            </div>
            <div class="thread-email-body" id="threadEmailBody${index}">
                <pre>${escapeHtml(email.body || 'No content')}</pre>
            </div>
        `;
        
        threadContent.appendChild(emailDiv);
    });
}

function toggleThreadEmail(index) {
    const body = document.getElementById(`threadEmailBody${index}`);
    body.classList.toggle('expanded');
}

function updateThreadWindow() {
    if (currentEmailId) {
        viewThread(currentEmailId);
    }
}

function closeThreadModal() {
    document.getElementById('threadModal').classList.remove('active');
    currentEmailId = null;
}

// Click outside modal to close
document.getElementById('emailModal').addEventListener('click', (e) => {
    if (e.target.id === 'emailModal') {
        closeEmailModal();
    }
});

document.getElementById('threadModal').addEventListener('click', (e) => {
    if (e.target.id === 'threadModal') {
        closeThreadModal();
    }
});

// Utility functions
function showLoading() {
    document.getElementById('loadingIndicator').classList.remove('hidden');
    document.getElementById('resultsTable').classList.add('hidden');
    document.getElementById('noResults').classList.add('hidden');
}

function hideLoading() {
    document.getElementById('loadingIndicator').classList.add('hidden');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
