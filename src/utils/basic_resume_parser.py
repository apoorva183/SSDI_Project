"""
Basic Resume Parser - Fallback when LLM parsing fails
Extracts basic information from resume text using pattern matching
"""

import re
from typing import Dict, Any

def parse_resume_basic(resume_text: str) -> Dict[str, Any]:
    """
    Basic resume parsing using regex patterns
    Fallback when LLM parsing is not available
    """
    
    # Clean up the text
    text = resume_text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Initialize result
    result = {
        "skills": "",
        "experience": "",
        "education": "",
        "projects": "",
        "contact": ""
    }
    
    # Extract Skills
    skills_patterns = [
        r"(?i)(?:skills?|technologies?|technical skills?)[:\s]*([^.]*?)(?:\.|experience|education|projects?|$)",
        r"(?i)(?:programming languages?|languages?)[:\s]*([^.]*?)(?:\.|experience|education|projects?|$)",
        r"(?i)(?:tools?|frameworks?|libraries?)[:\s]*([^.]*?)(?:\.|experience|education|projects?|$)"
    ]
    
    skills_found = []
    for pattern in skills_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        skills_found.extend([m.strip() for m in matches if m.strip()])
    
    if skills_found:
        result["skills"] = " • ".join(skills_found[:3])  # Top 3 skill sections
    
    # Extract Experience
    exp_patterns = [
        r"(?i)(?:experience|work experience|employment)[:\s]*([^.]*?)(?:\.|education|projects?|skills?|$)",
        r"(?i)(?:job|position|role)[:\s]*([^.]*?)(?:\.|education|projects?|skills?|$)"
    ]
    
    exp_found = []
    for pattern in exp_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        exp_found.extend([m.strip() for m in matches if m.strip()])
    
    if exp_found:
        result["experience"] = " • ".join(exp_found[:2])  # Top 2 experience sections
    
    # Extract Education
    edu_patterns = [
        r"(?i)(?:education|academic|degree|university|college)[:\s]*([^.]*?)(?:\.|experience|projects?|skills?|$)",
        r"(?i)(?:bachelor|master|phd|bs|ms|ba|ma)[:\s]*([^.]*?)(?:\.|experience|projects?|skills?|$)"
    ]
    
    edu_found = []
    for pattern in edu_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        edu_found.extend([m.strip() for m in matches if m.strip()])
    
    if edu_found:
        result["education"] = " • ".join(edu_found[:2])  # Top 2 education sections
    
    # Extract Projects
    proj_patterns = [
        r"(?i)(?:projects?|portfolio)[:\s]*([^.]*?)(?:\.|experience|education|skills?|$)"
    ]
    
    proj_found = []
    for pattern in proj_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        proj_found.extend([m.strip() for m in matches if m.strip()])
    
    if proj_found:
        result["projects"] = " • ".join(proj_found[:2])  # Top 2 project sections
    
    # Extract Contact Info
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phone_pattern = r'[\+]?[1-9]?[0-9]{3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
    
    emails = re.findall(email_pattern, text)
    phones = re.findall(phone_pattern, text)
    
    contact_info = []
    if emails:
        contact_info.append(f"Email: {emails[0]}")
    if phones:
        contact_info.append(f"Phone: {phones[0]}")
    
    if contact_info:
        result["contact"] = " • ".join(contact_info)
    
    # Clean up empty fields and truncate long ones
    for key, value in result.items():
        if isinstance(value, str):
            result[key] = value[:300] + "..." if len(value) > 300 else value
            if not result[key].strip():
                result[key] = f"Information extracted from {key} section"
    
    return result

def extract_key_info(resume_text: str) -> str:
    """Extract key information for search indexing"""
    parsed = parse_resume_basic(resume_text)
    
    # Combine all information for search
    search_text = " ".join([
        parsed.get("skills", ""),
        parsed.get("experience", ""), 
        parsed.get("education", ""),
        parsed.get("projects", "")
    ])
    
    return search_text.strip()