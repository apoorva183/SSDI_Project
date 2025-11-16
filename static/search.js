// static/search.js
document.addEventListener('DOMContentLoaded', () => {
    const box = document.getElementById('searchBox');
    const btn = document.getElementById('searchBtn');
    const out = document.getElementById('searchResults');
    const searchInfo = document.getElementById('searchInfo');
    const searchCapabilities = document.getElementById('searchCapabilities');

    // Load search capabilities on page load
    loadSearchCapabilities();

    function loadSearchCapabilities() {
        fetch('/api/search-capabilities')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const caps = data.capabilities;
                    const stats = data.statistics;
                    
                    let statusText = '';
                    if (caps.hybrid_search) {
                        statusText = `AI-powered hybrid search active (${stats.keyword_search.indexed_profiles} profiles, ${stats.semantic_search.total_embeddings} with semantic)`;
                    } else if (caps.keyword_search) {
                        statusText = `Keyword search active (${stats.keyword_search.indexed_profiles} profiles indexed)`;
                    } else {
                        statusText = 'Search not available';
                    }
                    
                    searchCapabilities.textContent = statusText;
                    searchInfo.style.display = 'block';
                }
            })
            .catch(err => {
                console.error('Failed to load search capabilities:', err);
                searchCapabilities.textContent = 'Search capabilities unknown';
                searchInfo.style.display = 'block';
            });
    }

    function render(results, searchData = {}) {
        if (!results || results.length === 0) {
            out.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search" style="color: #ccc;"></i>
                    <h3>No profiles found</h3>
                    <p>Try different keywords or check if student profiles exist in the system.</p>
                </div>
            `;
            return;
        }
        
        // Show search method info
        let searchMethodInfo = '';
        if (searchData.methods_used && searchData.methods_used.length > 0) {
            const methods = searchData.methods_used.join(' + ');
            const searchType = searchData.search_type || methods;
            searchMethodInfo = `
                <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #005035;">
                    <small style="color: #666;">
                        <i class="fas fa-cogs"></i> Search method: <strong>${searchType}</strong>
                        ${searchData.total_found ? ` • Found ${searchData.total_found} total matches` : ''}
                        ${searchData.semantic_available ? ' • AI semantic search active' : ''}
                    </small>
                </div>
            `;
        }
        out.innerHTML = `
            ${searchMethodInfo}
            <div style="margin-bottom: 25px; text-align: center;">
                <h3 style="color: #005035; font-size: 1.4em; margin: 0;">
                    Found ${results.length} student profile${results.length !== 1 ? 's' : ''}
                </h3>
            </div>
            ${results.map((r, idx) => `
                <div class="form-section">
                    <div style="display: flex; align-items: flex-start; gap: 15px; margin-bottom: 15px;">
                        <i class="fas fa-user-graduate" style="color: #A49665; font-size: 28px; margin-top: 5px;"></i>
                        <div style="flex: 1;">
                            <h3 style="margin: 0 0 8px 0; color: #005035; font-size: 1.4em;">
                                ${r.full_name || 'Unknown Student'}
                            </h3>
                            <p style="margin: 0; color: #666; font-size: 0.95em;">
                                <i class="fas fa-envelope" style="color: #A49665;"></i> 
                                ${r.email}
                            </p>
                            ${r.search_methods ? `
                                <p style="margin: 5px 0 0 0; color: #999; font-size: 0.8em;">
                                    <i class="fas fa-search"></i> Found by: ${r.search_methods.join(' + ')}
                                </p>
                            ` : ''}
                        </div>
                        <span class="score-badge">
                            Score: ${r.score.toFixed(2)}
                        </span>
                    </div>
                    ${r.snippet ? `
                        <div class="snippet-box">
                            ${r.snippet}
                        </div>
                    ` : ''}
                    <p style="color: #999; font-size: 0.85em; margin: 15px 0 0 0;">
                        <i class="fas fa-id-card" style="color: #A49665;"></i> 
                        Profile ID: ${r.profile_id.substring(0, 12)}...
                    </p>
                </div>
            `).join('')}
        `;
    }

    function showError(message) {
        out.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle" style="color: #ffc107;"></i>
                <h3>Search Error</h3>
                <p>${message}</p>
            </div>
        `;
    }

    function showLoading() {
        out.innerHTML = `
            <div class="empty-state">
                <div class="loading-spinner"></div>
                <p style="margin-top: 20px; color: #666;">Searching student profiles...</p>
            </div>
        `;
    }

    function doSearch() {
        const q = box.value.trim();
        if (!q) {
            out.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-keyboard" style="color: #A49665;"></i>
                    <h3>Ready to Search</h3>
                    <p>Enter keywords to search student profiles</p>
                </div>
            `;
            return;
        }

        showLoading();

        fetch(`/api/search?q=${encodeURIComponent(q)}`)
            .then(r => {
                if (!r.ok) {
                    throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                }
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    render(data.results, data);
                } else {
                    showError(data.error || 'Search failed');
                }
            })
            .catch(err => {
                console.error('Search error:', err);
                showError(`Network error: ${err.message}`);
            });
    }

    btn.addEventListener('click', doSearch);
    box.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
            doSearch();
        }
    });
    
    // Show initial message
    out.innerHTML = `
        <div class="empty-state">
            <i class="fas fa-search" style="color: #005035;"></i>
            <h3>Search Student Profiles</h3>
            <p>Enter keywords like skills, courses, or interests to find matching students</p>
            <p style="color: #999; font-size: 0.9em; margin-top: 15px;">
                <i class="fas fa-lightbulb" style="color: #A49665;"></i> 
                Try: "python machine learning", "react web development", "data science"
            </p>
        </div>
    `;
});
