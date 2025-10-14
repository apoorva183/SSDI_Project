// NinerMatch Review Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const profileForm = document.getElementById('profileForm');
    const successMessage = document.getElementById('successMessage');
    
    // Skill input handlers
    setupSkillInput('languageInput', 'languages');
    setupSkillInput('courseCompletedInput', 'coursesCompleted');
    setupSkillInput('currentCourseInput', 'currentCourses');
    setupSkillInput('certificationInput', 'certifications');
    setupSkillInput('technicalSkillInput', 'technicalSkills');
    setupSkillInput('softSkillInput', 'softSkills');
    setupSkillInput('academicInterestInput', 'academicInterests');
    setupSkillInput('personalInterestInput', 'personalInterests');
    setupSkillInput('conferenceInput', 'conferences');
    setupSkillInput('organizationInput', 'organizations');
    
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
    
    // Coursework
    if (data.coursework && Array.isArray(data.coursework)) {
        data.coursework.forEach(course => {
            const courseText = course.course_code ? 
                `${course.course_code}: ${course.course_title}` : 
                course.course_title;
            
            if (course.course_status === 'Completed') {
                addSkill('coursesCompleted', courseText);
            } else if (course.course_status === 'In Progress') {
                addSkill('currentCourses', courseText);
            }
        });
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
    
    // Professional experience (add to academic interests)
    if (data.professional_experience && Array.isArray(data.professional_experience)) {
        data.professional_experience.forEach(exp => {
            addSkill('academicInterests', `${exp.title} at ${exp.company}`);
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

function handleFormSubmit(e) {
    e.preventDefault();
    
    // Collect all form data
    const formData = {
        personal_info: {
            full_name: document.getElementById('fullName').value.trim(),
            email: document.getElementById('email').value.trim(),
            year: document.getElementById('year').value,
            program: document.getElementById('program').value.trim(),
            major: document.getElementById('major').value.trim()
        },
        background: {
            languages: collectLanguages('languages'),
            country_origin: document.getElementById('countryOrigin').value.trim()
        },
        academic: {
            courses_completed: collectSkills('coursesCompleted'),
            current_courses: collectSkills('currentCourses'),
            certifications: collectSkills('certifications')
        },
        skills: {
            technical: collectSkills('technicalSkills'),
            soft_skills: collectSkills('softSkills')
        },
        interests: {
            academic: collectSkills('academicInterests'),
            personal: collectSkills('personalInterests'),
            conferences: collectSkills('conferences'),
            organizations: collectSkills('organizations')
        }
    };
    
    // Validate required fields
    if (!formData.personal_info.full_name || !formData.personal_info.email || 
        !formData.personal_info.year || !formData.personal_info.program || 
        !formData.personal_info.major) {
        alert('Please fill in all required fields (marked with *).');
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
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Hide form and show success message
            document.querySelector('.profile-form').style.display = 'none';
            document.querySelector('.section-header').style.display = 'none';
            successMessage.style.display = 'block';
            
            // Data cleared from Flask session automatically
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