// Results Page JavaScript
class ResultsManager {
    constructor() {
        this.allConnections = [];
        this.filteredConnections = [];
        this.viewMode = 'grid'; // 'grid' only now
        
        this.init();
    }
    
    init() {
        // User email is handled by session on backend
        this.setupEventListeners();
        this.loadConnections();
    }
    
    setupEventListeners() {
        // Apply filters button
        document.getElementById('applyFilters')?.addEventListener('click', () => {
            this.applyFilters();
        });
        
        // Clear filters button
        document.getElementById('clearFilters')?.addEventListener('click', () => {
            this.clearFilters();
        });
        
        // Search input - real-time filtering
        document.getElementById('searchInput')?.addEventListener('input', (e) => {
            this.applyFilters();
        });
        
        // View toggle removed - using grid view only
        
        // Filter select changes
        document.getElementById('courseFilter')?.addEventListener('change', () => {
            this.applyFilters();
        });
        
        document.getElementById('skillFilter')?.addEventListener('change', () => {
            this.applyFilters();
        });
        
        document.getElementById('levelFilter')?.addEventListener('change', () => {
            this.applyFilters();
        });
        
        // Match type checkboxes
        document.querySelectorAll('.filter-checkbox input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.applyFilters();
            });
        });
    }
    
    addViewToggleButtons(isFreshView) {
        // Check if buttons already exist
        let buttonContainer = document.getElementById('viewToggleButtons');
        if (!buttonContainer) {
            buttonContainer = document.createElement('div');
            buttonContainer.id = 'viewToggleButtons';
            buttonContainer.className = 'view-toggle-buttons';
            buttonContainer.style.cssText = `
                display: flex;
                gap: 10px;
                margin: 20px 0;
                justify-content: center;
            `;
            
            // Insert after the page title
            const pageTitle = document.querySelector('h1');
            if (pageTitle && pageTitle.parentNode) {
                pageTitle.parentNode.insertBefore(buttonContainer, pageTitle.nextSibling);
            }
        }
        
        buttonContainer.innerHTML = `
            <button class="view-toggle-btn ${isFreshView ? 'active' : ''}" 
                    onclick="window.location.href='/results?fresh_only=true'">
                🆕 Fresh Session Results
            </button>
            <button class="view-toggle-btn ${!isFreshView ? 'active' : ''}" 
                    onclick="window.location.href='/results'">
                📚 All My Connections
            </button>
        `;
        
        // Add some basic styling
        const style = document.createElement('style');
        style.textContent = `
            .view-toggle-btn {
                padding: 10px 20px;
                border: 2px solid #A49665;
                background: transparent;
                color: #A49665;
                border-radius: 25px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .view-toggle-btn:hover {
                background: #A49665;
                color: white;
            }
            .view-toggle-btn.active {
                background: #A49665;
                color: white;
            }
        `;
        if (!document.querySelector('style[data-view-toggle]')) {
            style.setAttribute('data-view-toggle', 'true');
            document.head.appendChild(style);
        }
    }
    
    async loadConnections() {
        const loadingState = document.getElementById('loadingState');
        const resultsGrid = document.getElementById('resultsGrid');
        
        loadingState.style.display = 'block';
        resultsGrid.style.display = 'none';
        
        try {
            // Check if we should show fresh results only
            const urlParams = new URLSearchParams(window.location.search);
            const freshOnly = urlParams.get('fresh_only') === 'true';
            
            // User email handled by session on backend
            const apiUrl = freshOnly ? '/api/get-connections?fresh_only=true' : '/api/get-connections';
            console.log('📡 Loading connections:', freshOnly ? 'Fresh session only' : 'All connections');
            
            const response = await fetch(apiUrl);
            
            if (!response.ok) {
                throw new Error('Failed to load connections');
            }
            
            const data = await response.json();
            this.allConnections = data.connections || [];
            this.filteredConnections = [...this.allConnections];
            
            // Update page title and add navigation buttons based on mode
            const pageTitle = document.querySelector('h1');
            if (pageTitle) {
                if (freshOnly) {
                    pageTitle.textContent = 'Fresh Session Results';
                    this.addViewToggleButtons(true);
                } else {
                    pageTitle.textContent = 'All My Connections';
                    this.addViewToggleButtons(false);
                }
            }
            
            this.updateResultsCount();
            this.renderResults();
            
        } catch (error) {
            console.error('Error loading connections:', error);
            this.showEmptyState('Error loading connections. Please try again.');
        } finally {
            loadingState.style.display = 'none';
            resultsGrid.style.display = 'grid';
        }
    }
    
    applyFilters() {
        const searchTerm = document.getElementById('searchInput')?.value.toLowerCase() || '';
        const courseFilter = document.getElementById('courseFilter')?.value || '';
    const skillsFilter = document.getElementById('skillFilter')?.value || '';
        const levelFilter = document.getElementById('levelFilter')?.value || '';
        
        // Get match type checkboxes
        const likedByMe = document.getElementById('likedByMe')?.checked;
        const likedMe = document.getElementById('likedMe')?.checked;
        const mutualMatches = document.getElementById('mutualMatches')?.checked;
        
        this.filteredConnections = this.allConnections.filter(connection => {
            // Search filter
            if (searchTerm) {
                const name = connection.personal_info?.full_name?.toLowerCase() || '';
                if (!name.includes(searchTerm)) return false;
            }
            
            // Course filter
            if (courseFilter) {
                const courses = connection.academic?.courses || [];
                if (!courses.includes(courseFilter)) return false;
            }
            
            // Skills filter
            if (skillsFilter) {
                const skills = connection.skills?.technical || [];
                const hasSkill = skills.some(skill => 
                    skill.skillName?.toLowerCase() === skillsFilter.toLowerCase()
                );
                if (!hasSkill) return false;
            }
            
            // Academic level filter
            if (levelFilter) {
                const year = connection.personal_info?.year || '';
                if (year !== levelFilter) return false;
            }
            
            // Match type filter
            if (!likedByMe && !likedMe && !mutualMatches) {
                return true; // No match type filter applied
            }
            
            let matchesType = false;
            if (likedByMe && connection.likedByMe) matchesType = true;
            if (likedMe && connection.likedMe) matchesType = true;
            if (mutualMatches && connection.mutualMatch) matchesType = true;
            
            return matchesType;
        });
        
        this.updateResultsCount();
        this.renderResults();
    }
    
    clearFilters() {
        // Clear all form inputs
        document.getElementById('searchInput').value = '';
        document.getElementById('courseFilter').value = '';
    document.getElementById('skillFilter').value = '';
        document.getElementById('levelFilter').value = '';
        
        // Uncheck all checkboxes
        document.querySelectorAll('.filter-checkbox input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
        });
        
        // Reset to all connections
        this.filteredConnections = [...this.allConnections];
        this.updateResultsCount();
        this.renderResults();
    }
    
    // switchView method removed - using grid view only
    
    updateResultsCount() {
        const countElement = document.getElementById('resultsCount');
        if (countElement) {
            countElement.textContent = `(${this.filteredConnections.length})`;
        }
    }
    
    renderResults() {
        const resultsGrid = document.getElementById('resultsGrid');
        const emptyState = document.getElementById('emptyState');
        
        if (this.filteredConnections.length === 0) {
            resultsGrid.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }
        
        emptyState.style.display = 'none';
        resultsGrid.innerHTML = this.filteredConnections.map(connection => 
            this.createProfileTile(connection)
        ).join('');
        
        // Add event listeners to action buttons
        this.attachTileEventListeners();
    }
    
    createProfileTile(profile) {
        const fullName = profile.personal_info?.full_name || 'Anonymous Student';
        const major = profile.personal_info?.major || 'Undeclared';
        const year = profile.personal_info?.year || '';
        const email = profile.personal_info?.email || '';

        // Get initials for avatar
        const initials = fullName.split(' ')
            .map(n => n[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);

        // Calculate match score (use similarity if available)
        const matchScore = profile.similarity_score 
            ? Math.round(profile.similarity_score * 100) 
            : Math.floor(Math.random() * 30) + 70; // Fallback random score

        // Get top skills (limit to 3)
        const skills = profile.skills?.technical || [];
        const topSkills = skills.slice(0, 3).map(skill => skill.skillName);

        // Get courses (limit to 2)
        const courses = profile.academic?.courses || [];
        const topCourses = courses.slice(0, 2);

        // Favorite icon
        const favoriteIcon = profile.mutualMatch ? '❤️' : '🤍';
        const favoriteClass = profile.mutualMatch ? 'favorited' : '';

        // Show all relevant commonalities (limit to first 3 for space)
        let reason = '';
        if (profile.similarity_details) {
            const details = profile.similarity_details;
            if (details.commonalities && details.commonalities.length > 0) {
                const limitedCommonalities = details.commonalities.slice(0, 3);
                reason = limitedCommonalities.map(c => `<div style="margin-bottom:4px;font-size:0.9rem;">${c}</div>`).join('');
            } else {
                // Fallback to individual details
                let subreasons = [];
                if (details.shared_skills && details.shared_skills.length > 0) {
                    subreasons.push(`Shared skills: ${details.shared_skills.slice(0, 3).join(', ')}`);
                }
                if (details.shared_courses && details.shared_courses.length > 0) {
                    subreasons.push(`Common courses: ${details.shared_courses.slice(0, 2).join(', ')}`);
                }
                if (details.shared_languages && details.shared_languages.length > 0) {
                    subreasons.push(`Shared languages: ${details.shared_languages.join(', ')}`);
                }
                if (details.academic_level_match) {
                    subreasons.push('Same academic level');
                }
                reason = subreasons.slice(0, 3).length ? subreasons.slice(0, 3).map(c => `<div style="margin-bottom:4px;font-size:0.9rem;">${c}</div>`).join('') : '';
            }
        }
        if (!reason) {
            reason = '<div style="margin-bottom:4px;font-size:0.9rem;">You have similar academic backgrounds.</div>';
        }

        return `
            <div class="profile-tile" data-email="${email}">
                <div class="profile-tile-image">
                    <div class="profile-tile-avatar">${initials}</div>
                    <div class="favorite-icon ${favoriteClass}">${favoriteIcon}</div>
                </div>
                <div class="profile-tile-content">
                    <div class="profile-tile-header">
                        <h3 class="profile-tile-name">${fullName}</h3>
                        <p class="profile-tile-major">${major} ${year ? '• ' + year : ''}</p>
                        <span class="match-score">${matchScore}% Match</span>
                    </div>
                    <div style="color:#A49665;font-weight:600;margin-bottom:12px;max-height:90px;overflow-y:auto;line-height:1.4;">${reason}</div>
                    <div class="profile-tile-info">
                        ${topCourses.length > 0 ? `
                            <div class="info-row">
                                <div class="info-label">Courses</div>
                                <div class="info-tags">
                                    ${topCourses.map(course => `
                                        <span class="info-tag">${course}</span>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                    <div class="profile-tile-actions">
                        <button class="btn-profile" data-email="${email}">
                            👤 View Profile
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    attachTileEventListeners() {
        // Message buttons
        document.querySelectorAll('.btn-message').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const email = btn.dataset.email;
                this.openMessageDialog(email);
            });
        });
        
        // Profile buttons
        document.querySelectorAll('.btn-profile').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const email = btn.dataset.email;
                this.viewFullProfile(email);
            });
        });
        
        // Profile tile click
        document.querySelectorAll('.profile-tile').forEach(tile => {
            tile.addEventListener('click', (e) => {
                if (!e.target.closest('button')) {
                    const email = tile.dataset.email;
                    this.viewFullProfile(email);
                }
            });
        });
    }
    
    openMessageDialog(recipientEmail) {
        // TODO: Implement messaging functionality
        alert(`Opening chat with ${recipientEmail}...`);
        // Could redirect to a messaging page or open a modal
    }
    
    viewFullProfile(profileEmail) {
        // Find the profile from connections
        const profile = this.filteredConnections.find(c => c.personal_info?.email === profileEmail);
        
        if (!profile) {
            alert('Profile not found');
            return;
        }
        
        const fullName = profile.personal_info?.full_name || 'Student';
        const email = profile.personal_info?.email || 'Not available';
        const phone = profile.personal_info?.phone || 'Not available';
        const major = profile.personal_info?.major || 'Computer Science';
        const year = profile.personal_info?.year || 'Graduate';
        
        // Get initials for avatar
        const initials = fullName.split(' ')
            .map(n => n[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);
        
        // Create modal overlay
        const modal = document.createElement('div');
        modal.className = 'profile-modal-overlay';
        modal.innerHTML = `
            <div class="profile-modal">
                <button class="modal-close" onclick="this.closest('.profile-modal-overlay').remove()">×</button>
                <div class="modal-header">
                    <div class="modal-avatar">${initials}</div>
                    <h2>${fullName}</h2>
                    <p>${major} • ${year}</p>
                </div>
                <div class="modal-body">
                    <div class="contact-item">
                        <i class="fas fa-envelope"></i>
                        <div>
                            <strong>Email</strong>
                            <p>${email}</p>
                        </div>
                    </div>
                    <div class="contact-item">
                        <i class="fas fa-phone"></i>
                        <div>
                            <strong>Phone</strong>
                            <p>${phone}</p>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-close-modal" onclick="this.closest('.profile-modal-overlay').remove()">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    showEmptyState(message) {
        const emptyState = document.getElementById('emptyState');
        const resultsGrid = document.getElementById('resultsGrid');
        
        if (emptyState) {
            emptyState.querySelector('p').textContent = message || 'No connections found. Start swiping to find matches!';
            emptyState.style.display = 'block';
        }
        
        resultsGrid.innerHTML = '';
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    new ResultsManager();
});
