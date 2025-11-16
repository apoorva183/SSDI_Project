// NinerMatch Review Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const profileForm = document.getElementById('profileForm');
    const successMessage = document.getElementById('successMessage');
    
    // Skill input handlers
    setupSkillInput('languageInput', 'languages');
    setupSkillInput('certificationInput', 'certifications');
    setupSkillInput('technicalSkillInput', 'technicalSkills');
    setupSkillInput('softSkillInput', 'softSkills');
    setupSkillInput('academicInterestInput', 'academicInterests');
    setupSkillInput('personalInterestInput', 'personalInterests');
    setupSkillInput('conferenceInput', 'conferences');
    setupSkillInput('organizationInput', 'organizations');
    
    // Setup course search functionality
    setupCourseSearch();
    
    // Initialize with one empty experience item
    addExperienceItem();
    
    // Load parsed resume data
    loadParsedData();
    
    // Form submission
    profileForm.addEventListener('submit', handleFormSubmit);
});

function loadParsedData() {
    // Data is now loaded directly from Flask session via the template
    // The populateForm function is called directly in the HTML template
    console.log('Using server-side session data instead of sessionStorage');
}

function populateForm(data) {
    // Profile Information from LLM parser
    if (data.profile_information) {
        const info = data.profile_information;
        setFieldValue('fullName', info.full_name);
        setFieldValue('email', info.email);
        setFieldValue('program', info.program);
        setFieldValue('major', info.major);
        setFieldValue('year', info.academic_level);
    }
    
    // Languages with proficiency
    if (data.languages && Array.isArray(data.languages)) {
        data.languages.forEach(langObj => {
            addSkill('languages', langObj.language, langObj.languageProficiency);
        });
    }
    
    // Past Academic Profile Text
    if (data.past_academic_profile_text) {
        setFieldValue('pastAcademicProfile', data.past_academic_profile_text);
    }
    
    // Past academic profile text - could be used for country origin or additional info
    if (data.past_academic_profile_text) {
        // Extract country information if possible (basic parsing)
        const text = data.past_academic_profile_text.toLowerCase();
        if (text.includes('india')) {
            setFieldValue('countryOrigin', 'India');
        } else if (text.includes('china')) {
            setFieldValue('countryOrigin', 'China');
        } else if (text.includes('korea')) {
            setFieldValue('countryOrigin', 'South Korea');
        }
        // Add more country detection as needed
    }
    
   
 
    // Technical skills with proficiency
    if (data.technical_skills && Array.isArray(data.technical_skills)) {
        data.technical_skills.forEach(skillObj => {
            addSkill('technicalSkills', skillObj.skillName, skillObj.skillProficiency);
        });
    }
    
    // Soft skills (no proficiency)
    if (data.soft_skills && Array.isArray(data.soft_skills)) {
        data.soft_skills.forEach(skill => {
            addSkill('softSkills', skill);
        });
    }
    
    // Projects (add to academic interests)
    if (data.projects && Array.isArray(data.projects)) {
        data.projects.forEach(project => {
            addSkill('academicInterests', project.projectTitle);
        });
    }
    
    // Conferences
    if (data.conferences && Array.isArray(data.conferences)) {
        data.conferences.forEach(conf => {
            const confText = conf.title ? 
                `${conf.conferenceTitle} (${conf.title})` : 
                conf.conferenceTitle;
            addSkill('conferences', confText);
        });
    }
    
    // Professional experience - populate experience section
    if (data.professional_experience && Array.isArray(data.professional_experience)) {
        // Clear the initial empty experience item
        const experienceContainer = document.getElementById('experienceContainer');
        if (experienceContainer) {
            experienceContainer.innerHTML = '';
        }
        
        data.professional_experience.forEach(exp => {
            populateExperienceItem(exp);
        });
    }
}

function setFieldValue(id, value) {
    const field = document.getElementById(id);
    if (field && value) {
        field.value = value;
    }
}

function setCheckboxValue(id, value) {
    const checkbox = document.getElementById(id);
    if (checkbox) {
        checkbox.checked = !!value;
    }
}

function populateSkills(containerId, skills) {
    if (!Array.isArray(skills)) return;
    
    skills.forEach(skill => {
        if (skill && skill.trim()) {
            addSkill(containerId, skill.trim());
        }
    });
}

function setupSkillInput(inputId, containerId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const skill = input.value.trim();
            if (skill) {
                addSkill(containerId, skill);
                input.value = '';
            }
        }
    });
}

function addSkill(containerId, skillText, proficiency = null) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Check if skill already exists
    const existingSkills = Array.from(container.querySelectorAll('.skill-tag')).map(tag => {
        const textContent = tag.querySelector('.skill-text').textContent.trim();
        return textContent;
    });
    
    if (existingSkills.includes(skillText)) {
        return; // Don't add duplicates
    }
    
    const skillTag = document.createElement('div');
    skillTag.className = 'skill-tag';
    
    // Determine if this skill type needs proficiency
    const needsProficiency = containerId === 'technicalSkills' || containerId === 'languages';
    
    if (needsProficiency) {
        const defaultProficiency = proficiency || (containerId === 'languages' ? 'Fluent' : 'Intermediate');
        const proficiencyOptions = containerId === 'languages' 
            ? ['Native', 'Fluent', 'Intermediate', 'Beginner']
            : ['Advanced', 'Intermediate', 'Beginner'];
        
        skillTag.innerHTML = `
            <span class="skill-text">${skillText}</span>
            <select class="skill-proficiency" onchange="updateSkillProficiency(this)">
                ${proficiencyOptions.map(option => 
                    `<option value="${option}" ${option === defaultProficiency ? 'selected' : ''}>${option}</option>`
                ).join('')}
            </select>
            <button type="button" class="remove-skill" onclick="removeSkill(this)">×</button>
        `;
    } else {
        skillTag.innerHTML = `
            <span class="skill-text">${skillText}</span>
            <button type="button" class="remove-skill" onclick="removeSkill(this)">×</button>
        `;
    }
    
    container.appendChild(skillTag);
}

function updateSkillProficiency(selectElement) {
    // This function can be used for future enhancements if needed
    console.log('Skill proficiency updated:', selectElement.value);
}

function removeSkill(button) {
    button.parentElement.remove();
}

// Removed unused functions - no longer needed with new form structure

function setupCourseSearch() {
    const courseInput = document.getElementById('courseSearchInput');
    const resultsContainer = document.getElementById('courseSearchResults');
    const selectedContainer = document.getElementById('selectedCourses');
    
    if (!courseInput) return;
    
    let searchTimeout;
    
    courseInput.addEventListener('input', function() {
        const query = this.value.trim();
        
        clearTimeout(searchTimeout);
        
        if (query.length < 2) {
            resultsContainer.style.display = 'none';
            return;
        }
        
        searchTimeout = setTimeout(() => {
            searchCourses(query);
        }, 300);
    });
    
    courseInput.addEventListener('blur', function() {
        // Delay hiding to allow click on results
        setTimeout(() => {
            resultsContainer.style.display = 'none';
        }, 200);
    });
    
    courseInput.addEventListener('focus', function() {
        if (this.value.trim().length >= 2) {
            searchCourses(this.value.trim());
        }
    });
    
    function searchCourses(query) {
        fetch(`/api/search-courses?q=${encodeURIComponent(query)}&limit=10`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.courses) {
                    displayCourseResults(data.courses);
                }
            })
            .catch(error => {
                console.error('Course search error:', error);
            });
    }
    
    function displayCourseResults(courses) {
        if (courses.length === 0) {
            resultsContainer.style.display = 'none';
            return;
        }
        
        resultsContainer.innerHTML = '';
        
        courses.forEach(course => {
            const resultItem = document.createElement('div');
            resultItem.className = 'course-result-item';
            resultItem.innerHTML = `
                <div class="course-code">${course.full_code}</div>
                <div class="course-title">${course.title}</div>
            `;
            
            resultItem.addEventListener('click', () => {
                addCourse(course.display_text);
                courseInput.value = '';
                resultsContainer.style.display = 'none';
            });
            
            resultsContainer.appendChild(resultItem);
        });
        
        resultsContainer.style.display = 'block';
    }
    
    function addCourse(courseText) {
        // Check if course already exists
        const existingCourses = Array.from(selectedContainer.querySelectorAll('.skill-tag')).map(tag => {
            return tag.querySelector('.skill-text').textContent.trim();
        });
        
        if (existingCourses.includes(courseText)) {
            return; // Don't add duplicates
        }
        
        const courseTag = document.createElement('div');
        courseTag.className = 'skill-tag';
        courseTag.innerHTML = `
            <span class="skill-text">${courseText}</span>
            <button type="button" class="remove-skill" onclick="removeSkill(this)">×</button>
        `;
        
        selectedContainer.appendChild(courseTag);
    }
}

function collectCourses() {
    const container = document.getElementById('selectedCourses');
    if (!container) return [];
    
    const courseTags = container.querySelectorAll('.skill-tag');
    return Array.from(courseTags).map(tag => {
        return tag.querySelector('.skill-text').textContent.trim();
    });
}

function collectSkills(containerId) {
    const container = document.getElementById(containerId);
    const skillTags = container.querySelectorAll('.skill-tag');
    
    return Array.from(skillTags).map(tag => {
        const skillText = tag.querySelector('.skill-text').textContent.trim();
        const proficiencySelect = tag.querySelector('.skill-proficiency');
        
        if (proficiencySelect) {
            // Return object with skill name and proficiency
            return {
                skillName: skillText,
                skillProficiency: proficiencySelect.value
            };
        } else {
            // Return just the skill name for skills without proficiency
            return skillText;
        }
    });
}

function collectLanguages(containerId) {
    const container = document.getElementById(containerId);
    const skillTags = container.querySelectorAll('.skill-tag');
    
    return Array.from(skillTags).map(tag => {
        const languageText = tag.querySelector('.skill-text').textContent.trim();
        const proficiencySelect = tag.querySelector('.skill-proficiency');
        
        return {
            language: languageText,
            languageProficiency: proficiencySelect ? proficiencySelect.value : 'Fluent'
        };
    });
}

function collectDynamicEntries(containerSelector, fields) {
    const entries = document.querySelectorAll(`${containerSelector} .dynamic-entry`);
    return Array.from(entries).map(entry => {
        const data = {};
        fields.forEach(field => {
            const input = entry.querySelector(`[name="${field}"]`);
            if (input) {
                data[field.split('_')[1]] = input.value.trim();
            }
        });
        return data;
    }).filter(entry => Object.values(entry).some(value => value !== ''));
}

// Experience handling functions
function addExperienceItem(experienceData = null) {
    const container = document.getElementById('experienceContainer');
    if (!container) return;
    
    const experienceId = 'experience_' + Date.now() + Math.random().toString(36).substr(2, 9);
    
    const experienceDiv = document.createElement('div');
    experienceDiv.className = 'experience-item';
    experienceDiv.setAttribute('data-experience-id', experienceId);
    
    experienceDiv.innerHTML = `
        <div class="experience-header">
            <h4><i class="fas fa-briefcase"></i> Experience ${container.children.length + 1}</h4>
            <button type="button" class="btn-remove-experience" onclick="removeExperienceItem('${experienceId}')">
                <i class="fas fa-trash"></i> Remove
            </button>
        </div>
        <div class="form-grid">
            <div class="form-group">
                <label>Job Title *</label>
                <input type="text" name="exp_title_${experienceId}" value="${experienceData?.title || ''}" 
                       placeholder="e.g., Software Engineering Intern" required>
            </div>
            <div class="form-group">
                <label>Company *</label>
                <input type="text" name="exp_company_${experienceId}" value="${experienceData?.company || ''}" 
                       placeholder="e.g., Microsoft, Google, IBM" required>
            </div>
            <div class="form-group">
                <label>Start Date</label>
                <input type="text" name="exp_startDate_${experienceId}" value="${experienceData?.startDate || ''}" 
                       placeholder="e.g., 2023-06, June 2023">
            </div>
            <div class="form-group">
                <label>End Date</label>
                <input type="text" name="exp_endDate_${experienceId}" value="${experienceData?.endDate || ''}" 
                       placeholder="e.g., 2023-08, Present">
            </div>
            <div class="form-group">
                <label>Status *</label>
                <select name="exp_status_${experienceId}" required>
                    <option value="">Select status</option>
                    <option value="Past" ${experienceData?.status === 'Past' ? 'selected' : ''}>Past</option>
                    <option value="Current Job" ${experienceData?.status === 'Current Job' ? 'selected' : ''}>Current Job</option>
                </select>
            </div>
            <div class="form-group full-width">
                <label>Job Description</label>
                <textarea name="exp_jobDescription_${experienceId}" rows="3" 
                          placeholder="Describe your responsibilities and achievements...">${experienceData?.jobDescription || ''}</textarea>
            </div>
        </div>
    `;
    
    container.appendChild(experienceDiv);
    updateExperienceNumbers();
}

function removeExperienceItem(experienceId) {
    const experienceItem = document.querySelector(`[data-experience-id="${experienceId}"]`);
    if (experienceItem) {
        experienceItem.remove();
        updateExperienceNumbers();
    }
}

function updateExperienceNumbers() {
    const container = document.getElementById('experienceContainer');
    if (!container) return;
    
    const experienceItems = container.querySelectorAll('.experience-item');
    experienceItems.forEach((item, index) => {
        const header = item.querySelector('.experience-header h4');
        if (header) {
            header.innerHTML = `<i class="fas fa-briefcase"></i> Experience ${index + 1}`;
        }
    });
}

function populateExperienceItem(expData) {
    addExperienceItem(expData);
}

function collectExperience() {
    const container = document.getElementById('experienceContainer');
    if (!container) return [];
    
    const experienceItems = container.querySelectorAll('.experience-item');
    const experiences = [];
    
    experienceItems.forEach(item => {
        const experienceId = item.getAttribute('data-experience-id');
        
        const title = item.querySelector(`[name="exp_title_${experienceId}"]`)?.value.trim() || '';
        const company = item.querySelector(`[name="exp_company_${experienceId}"]`)?.value.trim() || '';
        const startDate = item.querySelector(`[name="exp_startDate_${experienceId}"]`)?.value.trim() || '';
        const endDate = item.querySelector(`[name="exp_endDate_${experienceId}"]`)?.value.trim() || '';
        const status = item.querySelector(`[name="exp_status_${experienceId}"]`)?.value || '';
        const jobDescription = item.querySelector(`[name="exp_jobDescription_${experienceId}"]`)?.value.trim() || '';
        
        // Only include experience if at least title and company are filled
        if (title && company) {
            experiences.push({
                title,
                company,
                startDate: startDate || null,
                endDate: endDate || null,
                status,
                jobDescription
            });
        }
    });
    
    return experiences;
}

function handleFormSubmit(e) {
    e.preventDefault();
    
    // Collect all form data
    const formData = {
        personal_info: {
            full_name: document.getElementById('fullName').value.trim(),
            email: document.getElementById('email').value.trim(),
            password: document.getElementById('password').value,
            year: document.getElementById('year').value,
            program: document.getElementById('program').value.trim(),
            major: document.getElementById('major').value.trim()
        },
        background: {
            languages: collectLanguages('languages'),
            country_origin: document.getElementById('countryOrigin').value.trim()
        },
        academic: {
            courses: collectCourses(),
            certifications: collectSkills('certifications')
        },
        past_academic_profile_text: document.getElementById('pastAcademicProfile').value.trim(),
        skills: {
            technical: collectSkills('technicalSkills'),
            soft_skills: collectSkills('softSkills')
        },
        interests: {
            academic: collectSkills('academicInterests'),
            personal: collectSkills('personalInterests'),
            conferences: collectSkills('conferences'),
            organizations: collectSkills('organizations')
        },
        professional_experience: collectExperience()
    };
    
    // Validate required fields
    if (!formData.personal_info.full_name || !formData.personal_info.email || 
        !formData.personal_info.password || !formData.personal_info.year || 
        !formData.personal_info.program || !formData.personal_info.major) {
        alert('Please fill in all required fields (marked with *).');
        return;
    }
    
    // Validate password length
    if (formData.personal_info.password.length < 6) {
        alert('Password must be at least 6 characters long.');
        return;
    }
    
    // Submit to backend
    submitProfile(formData);
}

function submitProfile(profileData) {
    // Show loading state
    const submitBtn = document.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitBtn.disabled = true;
    
    fetch('/submit_profile', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(profileData)
    })
    .then(response => {
        // Always parse JSON first, then check status
        return response.json().then(data => {
            if (!response.ok) {
                // Throw error with the actual server error message
                throw new Error(data.error || `Server error: ${response.status}`);
            }
            return data;
        });
    })
    .then(data => {
        if (data.success) {
            // Show success message
            alert('Profile created successfully! You are now logged in. Redirecting to Find Matches...');
            
            // Redirect to matches page after successful registration
            window.location.href = '/matches';
        } else {
            throw new Error(data.error || 'Failed to save profile');
        }
    })
    .catch(error => {
        alert('Failed to save profile: ' + error.message);
        console.error('Submit error:', error);
    })
    .finally(() => {
        // Restore button state
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}