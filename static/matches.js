// Matches Page JavaScript
class SwipeManager {
    constructor() {
        this.matches = [];
        this.currentIndex = 0;
        this.currentCard = null;
        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.cardStack = document.getElementById('cardStack');
        this.userEmail = '';
        this.userId = null;
        
        // Swipe limit settings
        this.SWIPE_LIMIT = 5; // Minimum swipes before showing results
        this.swipeCount = 0;
        this.hasReachedLimit = false;
        
        this.initializeElements();
        this.bindEvents();
    }
    
    initializeElements() {
        this.matchStats = document.getElementById('matchStats');
        this.matchCount = document.getElementById('matchCount');
        this.currentCardSpan = document.getElementById('currentCard');
        this.actionButtons = document.getElementById('actionButtons');
        this.passBtn = document.getElementById('passBtn');
        this.likeBtn = document.getElementById('likeBtn');
        this.loadingScreen = document.getElementById('loadingScreen');
        this.noMoreCards = document.getElementById('noMoreCards');
        this.refreshBtn = document.getElementById('refreshBtn');
    }
    
    bindEvents() {
        // Action buttons
        this.passBtn.addEventListener('click', () => this.swipeLeft());
        this.likeBtn.addEventListener('click', () => this.swipeRight());
        
        // Refresh button
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.findMatches());
        }
        
        // Auto-load matches on page load
        this.findMatches();
    }
    
    async findMatches() {
        console.log('🔍 Starting search for matches...');
        this.showLoading(true);
        this.hideElements();
        
        // Reset swipe counters for new session
        this.swipeCount = 0;
        this.hasReachedLimit = false;
        this.currentIndex = 0;
        
        // Clear any existing view results button
        const existingBtn = document.getElementById('permanentViewResultsBtn');
        if (existingBtn) existingBtn.remove();
        
        try {
            // Start a fresh session to reset swipe tracking
            console.log('🔄 Starting fresh swipe session...');
            await fetch('/api/start-fresh-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            // User email is handled by session on backend
            const url = `/api/find-matches`;
            console.log('🌐 Making API call to:', url);
            
            const response = await fetch(url);
            console.log('📡 Response status:', response.status);
            
            const data = await response.json();
            console.log('📊 Response data:', data);
            
            if (data.success) {
                this.matches = data.matches;
                this.currentIndex = 0;
                
                if (this.matches.length > 0) {
                    // Generate userId based on timestamp (backend uses user_email from session)
                    this.userId = '_' + Date.now();
                    this.updateMatchStats();
                    this.showNextCard();
                    this.showElements();
                } else {
                    this.showNoMatches();
                }
            } else {
                alert(data.error || 'Failed to find matches');
            }
        } catch (error) {
            console.error('Error finding matches:', error);
            alert('Error connecting to server');
        } finally {
            this.showLoading(false);
        }
    }
    
    generateUserId(email) {
        // Simple user ID generation - in production, this should come from your auth system
        return email.split('@')[0] + '_' + Date.now();
    }
    
    showLoading(show) {
        this.loadingScreen.style.display = show ? 'flex' : 'none';
    }
    
    hideElements() {
        if (this.matchStats) this.matchStats.style.display = 'none';
        if (this.actionButtons) this.actionButtons.style.display = 'none';
        if (this.noMoreCards) this.noMoreCards.style.display = 'none';
    }
    
    showElements() {
        if (this.matchStats) this.matchStats.style.display = 'flex';
        if (this.actionButtons) this.actionButtons.style.display = 'flex';
    }
    
    updateMatchStats() {
        // Only update if elements exist
        if (this.matchCount) {
            this.matchCount.textContent = `${this.matches.length} matches found`;
        }
        if (this.currentCardSpan) {
            this.currentCardSpan.textContent = `Card ${this.currentIndex + 1} of ${this.matches.length}`;
        }
        // Show controls when we have match stats (if controls exist)
        const controls = document.querySelector('.controls');
        if (controls) controls.style.display = 'block';
    }
    
    showNextCard() {
        if (this.currentIndex >= this.matches.length) {
            this.showNoMoreCards();
            return;
        }
        
        const match = this.matches[this.currentIndex];
        this.currentCard = this.createProfileCard(match);
        this.cardStack.appendChild(this.currentCard);
        
        // Add touch/mouse events for swiping
        this.addSwipeEvents(this.currentCard);
        
        this.updateMatchStats();
    }
    
    createProfileCard(match) {
        const card = document.createElement('div');
        card.className = 'profile-card';

        const profile = match.profile;
        const similarity = match.similarity;

        // Calculate similarity percentage
        const similarityPercent = Math.round(similarity.overall_score * 100);

        // Get similarity details for reason
        const details = similarity.similarity_details || {};
        let reason = '';
        
        // Use commonalities directly if available
        if (details.commonalities && details.commonalities.length > 0) {
            reason = details.commonalities[0]; // Use the first commonality as primary reason
        } else {
            // Fallback to individual details
            if (details.shared_skills && details.shared_skills.length > 0) {
                reason += `Shared skills: ${details.shared_skills.join(', ')}. `;
            }
            if (details.shared_courses && details.shared_courses.length > 0) {
                reason += `Common courses: ${details.shared_courses.join(', ')}. `;
            }
            if (details.shared_languages && details.shared_languages.length > 0) {
                reason += `Shared languages: ${details.shared_languages.join(', ')}. `;
            }
            if (details.academic_level_match) {
                reason += 'Same academic level. ';
            }
        }
        
        if (!reason) {
            reason = 'You have similar academic backgrounds.';
        }

        // Use the REAL name from the profile, not "Anonymous"
        const fullName = profile.full_name || profile.name || 'Student';
        console.log('👤 Displaying profile for:', fullName);
        console.log('📚 Academic background data:', profile.past_academic_background);
        console.log('📋 Full profile object:', profile);

        // Generate initials for avatar
        const initials = fullName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

        card.innerHTML = `
            <div class="profile-image">
                <div class="profile-avatar">${initials}</div>
            </div>
            <div class="profile-info">
                <div class="profile-header">
                    <h2 class="profile-name">${fullName}</h2>
                    <div class="similarity-badge">${similarityPercent}% Match</div>
                    <div class="profile-details">${profile.major || 'Computer Science'} • ${profile.academic_level || 'Graduate'}</div>
                </div>
                <div class="info-section">
                    <div style="color:#A49665;font-weight:600;margin-bottom:8px;">${reason}</div>
                </div>
                <div class="info-section">
                    <h4>Academic Background</h4>
                    <div class="skills-container">
                        <span class="skill-tag">${profile.past_academic_background && profile.past_academic_background.trim() ? profile.past_academic_background : 'No academic history available.'}</span>
                    </div>
                </div>
                ${profile.courses_taken && profile.courses_taken.length > 0 ? `
                <div class="info-section">
                    <h4>Can offer help with</h4>
                    <div class="skills-container">
                        ${profile.courses_taken.slice(0, 5).map(course => {
                            const courseName = typeof course === 'object' ? (course.name || course.course || 'Unknown Course') : course;
                            return `<span class="skill-tag">${courseName}</span>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;

        return card;
    }
    
    generateCommonalities(similarityDetails) {
        const commonalities = [];
        
        if (similarityDetails.shared_skills && similarityDetails.shared_skills.length > 0) {
            commonalities.push(`${similarityDetails.shared_skills.length} shared skills`);
        }
        
        if (similarityDetails.shared_courses && similarityDetails.shared_courses.length > 0) {
            commonalities.push(`${similarityDetails.shared_courses.length} common courses`);
        }
        
        if (similarityDetails.shared_languages && similarityDetails.shared_languages.length > 0) {
            commonalities.push(`${similarityDetails.shared_languages.length} shared languages`);
        }
        
        if (similarityDetails.academic_level_match) {
            commonalities.push('Same academic level');
        }
        
        return commonalities;
    }
    
    addSwipeEvents(card) {
        // Mouse events
        card.addEventListener('mousedown', (e) => this.startSwipe(e));
        document.addEventListener('mousemove', (e) => this.onSwipe(e));
        document.addEventListener('mouseup', () => this.endSwipe());
        
        // Touch events
        card.addEventListener('touchstart', (e) => this.startSwipe(e.touches[0]));
        document.addEventListener('touchmove', (e) => this.onSwipe(e.touches[0]));
        document.addEventListener('touchend', () => this.endSwipe());
    }
    
    startSwipe(pointer) {
        if (!this.currentCard) return;
        
        this.isDragging = true;
        this.startX = pointer.clientX;
        this.startY = pointer.clientY;
        
        this.currentCard.style.transition = 'none';
    }
    
    onSwipe(pointer) {
        if (!this.isDragging || !this.currentCard || !pointer) return;
        
        this.currentX = pointer.clientX - this.startX;
        this.currentY = pointer.clientY - this.startY;
        
        const rotation = this.currentX * 0.1;
        const opacity = 1 - Math.abs(this.currentX) / 300;
        
        this.currentCard.style.transform = `translate(${this.currentX}px, ${this.currentY}px) rotate(${rotation}deg)`;
        this.currentCard.style.opacity = opacity;
        
        // Add visual feedback
        if (this.currentX > 50) {
            this.currentCard.classList.add('swiping-right');
            this.currentCard.classList.remove('swiping-left');
        } else if (this.currentX < -50) {
            this.currentCard.classList.add('swiping-left');
            this.currentCard.classList.remove('swiping-right');
        } else {
            this.currentCard.classList.remove('swiping-right', 'swiping-left');
        }
    }
    
    endSwipe() {
        if (!this.isDragging || !this.currentCard) return;
        
        this.isDragging = false;
        this.currentCard.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
        
        const swipeThreshold = 100;
        
        if (this.currentX > swipeThreshold) {
            this.completeSwipeRight();
        } else if (this.currentX < -swipeThreshold) {
            this.completeSwipeLeft();
        } else {
            // Snap back to center
            this.currentCard.style.transform = 'translate(0px, 0px) rotate(0deg)';
            this.currentCard.style.opacity = '1';
            this.currentCard.classList.remove('swiping-right', 'swiping-left');
        }
    }
    
    swipeRight() {
        if (this.currentCard) {
            this.currentCard.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
            this.completeSwipeRight();
        }
    }
    
    swipeLeft() {
        if (this.currentCard) {
            this.currentCard.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
            this.completeSwipeLeft();
        }
    }
    
    completeSwipeRight() {
        this.currentCard.classList.add('swiped-right');
        this.recordSwipeFeedback('like');
        this.incrementSwipeCount();
        
        setTimeout(() => {
            this.nextCard();
        }, 300);
    }
    
    completeSwipeLeft() {
        this.currentCard.classList.add('swiped-left');
        this.recordSwipeFeedback('dislike');
        this.incrementSwipeCount();
        
        setTimeout(() => {
            this.nextCard();
        }, 300);
    }
    
    incrementSwipeCount() {
        this.swipeCount++;
        console.log(`🔢 Swipe count: ${this.swipeCount}/${this.SWIPE_LIMIT}`);
        
        // Check if user has reached the swipe limit
        if (this.swipeCount >= this.SWIPE_LIMIT && !this.hasReachedLimit) {
            this.hasReachedLimit = true;
            this.showSwipeLimitReached();
        }
        
        // Update swipe progress indicator if it exists
        this.updateSwipeProgress();
    }
    
    updateSwipeProgress() {
        const progressElement = document.getElementById('swipeProgress');
        if (progressElement) {
            const percentage = Math.min((this.swipeCount / this.SWIPE_LIMIT) * 100, 100);
            progressElement.style.width = `${percentage}%`;
            
            const progressText = document.getElementById('swipeProgressText');
            if (progressText) {
                progressText.textContent = `${this.swipeCount} / ${this.SWIPE_LIMIT} swipes`;
            }
        }
    }
    
    showSwipeLimitReached() {
        // Create overlay notification
        const overlay = document.createElement('div');
        overlay.className = 'swipe-limit-overlay';
        overlay.innerHTML = `
            <div class="swipe-limit-modal">
                <div class="swipe-limit-icon">✨</div>
                <h2>Great Job!</h2>
                <p>You've swiped on enough profiles to see your connections!</p>
                <div class="swipe-limit-stats">
                    <div class="stat">
                        <span class="stat-number">${this.swipeCount}</span>
                        <span class="stat-label">Swipes Made</span>
                    </div>
                </div>
                <div class="swipe-limit-actions">
                    <button class="btn-view-results" id="viewResultsBtn">
                        👥 View My Connections
                    </button>
                    <button class="btn-keep-swiping" id="keepSwipingBtn">
                        ➡️ Keep Swiping
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // Add event listeners
        document.getElementById('viewResultsBtn').addEventListener('click', () => {
            this.navigateToResults();
        });
        
        document.getElementById('keepSwipingBtn').addEventListener('click', () => {
            overlay.remove();
        });
        
        // Also add a permanent button to the UI
        this.addViewResultsButton();
    }
    
    addViewResultsButton() {
        // Check if button already exists
        if (document.getElementById('permanentViewResultsBtn')) return;
        
        const actionButtons = document.getElementById('actionButtons');
        if (actionButtons) {
            const viewResultsBtn = document.createElement('button');
            viewResultsBtn.id = 'permanentViewResultsBtn';
            viewResultsBtn.className = 'view-results-btn';
            viewResultsBtn.innerHTML = '👥 View Connections';
            viewResultsBtn.addEventListener('click', () => this.navigateToResults());
            
            actionButtons.appendChild(viewResultsBtn);
        }
    }
    
    navigateToResults() {
        // Navigate to results with fresh_only flag to show only current session results
        window.location.href = `/results?fresh_only=true`;
    }
    
    superConnect() {
        if (this.currentCard) {
            this.currentCard.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
            this.currentCard.style.transform = 'scale(1.1) rotate(5deg)';
            this.currentCard.style.opacity = '0';
            this.recordSwipeFeedback('super_like');
            
            setTimeout(() => {
                this.nextCard();
            }, 400);
        }
    }
    
    async recordSwipeFeedback(feedback) {
        if (!this.matches[this.currentIndex]) return;
        
        const match = this.matches[this.currentIndex];
        const matchedProfileId = match.profile.profile_id || match.profile.email || match.profile.name;
        
        console.log('📝 Recording swipe:', {
            user_id: this.userId,
            user_email: this.userEmail,
            matched_user_id: matchedProfileId,
            matched_email: match.profile.email || 'unknown',
            feedback: feedback
        });
        
        try {
            const response = await fetch('/api/swipe-feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: this.userId,
                    user_email: this.userEmail,  // Add user email for easier lookup
                    matched_user_id: matchedProfileId,
                    matched_user_email: match.profile.email,  // Add matched email
                    feedback: feedback,
                    similarity_features: match.similarity.similarity_details || {}
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                console.warn('Failed to record feedback:', data.error);
            } else {
                console.log('✅ Swipe feedback recorded successfully');
            }
        } catch (error) {
            console.error('Error recording feedback:', error);
        }
    }
    
    nextCard() {
        if (this.currentCard) {
            this.currentCard.remove();
            this.currentCard = null;
        }
        
        this.currentIndex++;
        
        if (this.currentIndex < this.matches.length) {
            this.showNextCard();
        } else {
            this.showNoMoreCards();
        }
    }
    
    // Match modal functionality removed
    
    showNoMoreCards() {
        this.hideElements();
        
        // If user has made enough swipes, automatically redirect to results
        if (this.swipeCount >= this.SWIPE_LIMIT || this.swipeCount >= 5) {
            // Show completion message
            this.noMoreCards.style.display = 'flex';
            const emptyState = this.noMoreCards.querySelector('.empty-state');
            emptyState.innerHTML = `
                <div class="completion-message">
                    <h2>🌟 All Caught Up!</h2>
                    <p>You've seen all available matches. Check back later for new connections!</p>
                    <button class="find-new-matches-btn" onclick="window.location.reload()">Find New Matches</button>
                    <button class="view-results-btn" onclick="window.location.href='/results'">📊 View My Connections</button>
                </div>
            `;
            
            setTimeout(() => {
                console.log('🔄 Auto-redirecting to fresh results after completing swipes');
                window.location.href = '/results?fresh_only=true';
            }, 3000);  // Give user time to read the message
        } else {
            this.noMoreCards.style.display = 'flex';
        }
    }
    
    showNoMatches() {
        this.hideElements();
        this.noMoreCards.style.display = 'flex';
        
        const emptyState = this.noMoreCards.querySelector('.empty-state');
        emptyState.innerHTML = `
            <h2>🔍 No Matches Found</h2>
            <p>We couldn't find any study partners for you right now. Try updating your profile or check back later!</p>
            <button class="refresh-btn" onclick="window.location.href='/'">Update Profile</button>
        `;
    }
}

// Initialize the swipe manager when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new SwipeManager();
});