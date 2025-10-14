# Data models for student profiles

from datetime import datetime
from typing import Dict, Any
from bson import ObjectId
import hashlib

class ProfileModel:
    @staticmethod
    def create_profile_schema(profile_data: Dict[str, Any]) -> Dict[str, Any]:
        
        # Generate profile ID and metadata
        profile_id = str(ObjectId())
        created_at = datetime.utcnow()
        
        # Create the complete profile document
        profile_doc = {
            "_id": ObjectId(profile_id),
            "profile_id": profile_id,
            "created_at": created_at,
            "updated_at": created_at,
            "status": "active",  # active, inactive, suspended
            
            # Basic Profile Information
            "personal_info": {
                "full_name": profile_data.get("personal_info", {}).get("full_name", ""),
                "email": profile_data.get("personal_info", {}).get("email", ""),
                "year": profile_data.get("personal_info", {}).get("year", ""),
                "program": profile_data.get("personal_info", {}).get("program", ""),
                "major": profile_data.get("personal_info", {}).get("major", ""),
                "email_hash": hashlib.md5(profile_data.get("personal_info", {}).get("email", "").encode()).hexdigest()
            },
            
            # Background & Languages (now with proficiency levels)
            "background": {
                "languages": profile_data.get("background", {}).get("languages", []),
                "country_origin": profile_data.get("background", {}).get("country_origin", ""),
                "international_student": profile_data.get("background", {}).get("country_origin", "") not in ["", "United States", "USA"]
            },
            
            # Academic Details
            "academic": {
                "courses_completed": profile_data.get("academic", {}).get("courses_completed", []),
                "current_courses": profile_data.get("academic", {}).get("current_courses", []),
                "certifications": profile_data.get("academic", {}).get("certifications", []),
                "gpa": profile_data.get("academic", {}).get("gpa", None),
                "graduation_year": profile_data.get("academic", {}).get("graduation_year", None)
            },
            
            # Skills (now with individual proficiency levels)
            "skills": {
                "technical": profile_data.get("skills", {}).get("technical", []),
                "soft_skills": profile_data.get("skills", {}).get("soft_skills", [])
            },
            
            # Interests & Activities
            "interests": {
                "academic": profile_data.get("interests", {}).get("academic", []),
                "personal": profile_data.get("interests", {}).get("personal", []),
                "conferences": profile_data.get("interests", {}).get("conferences", []),
                "organizations": profile_data.get("interests", {}).get("organizations", [])
            },
            
            # Resume/PDF Information
            "resume": {
                "uploaded": False,
                "file_id": None,
                "filename": None,
                "upload_date": None,
                "processed": False
            },
            
            # LLM Parsed Backup - stores original parsed data from resume
            "llm_parsed_backup": profile_data.get("llm_parsed_backup", None)
        }
        
        return profile_doc

# Schema validation function
def validate_profile_data(data: Dict[str, Any]) -> Dict[str, list]:
    """Validate profile data and return any errors"""
    errors = {}
    
    # Required fields
    required_fields = {
        "personal_info.full_name": "Full name is required",
        "personal_info.email": "Email is required",
        "personal_info.year": "Academic year is required",
        "personal_info.program": "Program is required",
        "personal_info.major": "Major is required"
    }
    
    for field_path, error_msg in required_fields.items():
        keys = field_path.split('.')
        value = data
        try:
            for key in keys:
                value = value.get(key, "")
            if not value or not str(value).strip():
                if "required" not in errors:
                    errors["required"] = []
                errors["required"].append(error_msg)
        except (AttributeError, TypeError):
            if "required" not in errors:
                errors["required"] = []
            errors["required"].append(error_msg)
    
    # Email validation
    email = data.get("personal_info", {}).get("email", "")
    if email and "@" not in email:
        if "format" not in errors:
            errors["format"] = []
        errors["format"].append("Invalid email format")
    
    return errors