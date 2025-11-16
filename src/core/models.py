from datetime import datetime
from typing import Dict, Any
from bson import ObjectId
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash

class ProfileModel:
    @staticmethod
    def create_profile_schema(profile_data: Dict[str, Any]) -> Dict[str, Any]:
        profile_id = str(ObjectId())
        created_at = datetime.utcnow()
        
        profile_doc = {
            "_id": ObjectId(profile_id),
            "profile_id": profile_id,
            "created_at": created_at,
            "updated_at": created_at,
            "status": "active",
            
            "personal_info": {
                "full_name": profile_data.get("personal_info", {}).get("full_name", ""),
                "email": profile_data.get("personal_info", {}).get("email", ""),
                "password_hash": profile_data.get("personal_info", {}).get("password_hash", ""),
                "year": profile_data.get("personal_info", {}).get("year", ""),
                "program": profile_data.get("personal_info", {}).get("program", ""),
                "major": profile_data.get("personal_info", {}).get("major", ""),
                "email_hash": hashlib.md5(profile_data.get("personal_info", {}).get("email", "").encode()).hexdigest()
            },
            
            "background": {
                "languages": profile_data.get("background", {}).get("languages", []),
                "country_origin": profile_data.get("background", {}).get("country_origin", ""),
                "international_student": profile_data.get("background", {}).get("country_origin", "") not in ["", "United States", "USA"]
            },
            
            "academic": {
                "courses": profile_data.get("academic", {}).get("courses", []),
                "certifications": profile_data.get("academic", {}).get("certifications", []),
                "past_academic_profile_text": (
                    profile_data.get("past_academic_profile_text", "") or
                    profile_data.get("llm_parsed_backup", {}).get("past_academic_profile_text", "")
                ),
                "gpa": profile_data.get("academic", {}).get("gpa", None),
                "graduation_year": profile_data.get("academic", {}).get("graduation_year", None),
                "previous_degrees": (
                    profile_data.get("previous_degrees", []) or
                    profile_data.get("llm_parsed_backup", {}).get("previous_degrees", [])
                ),
                "previous_institutions": (
                    profile_data.get("previous_institutions", []) or
                    profile_data.get("llm_parsed_backup", {}).get("previous_institutions", [])
                ),
                "graduation_years": (
                    profile_data.get("graduation_years", []) or
                    profile_data.get("llm_parsed_backup", {}).get("graduation_years", [])
                )
            },
            
            "skills": {
                "technical": profile_data.get("skills", {}).get("technical", []),
                "soft_skills": profile_data.get("skills", {}).get("soft_skills", [])
            },
            
            "interests": {
                "academic": profile_data.get("interests", {}).get("academic", []),
                "personal": profile_data.get("interests", {}).get("personal", []),
                "conferences": profile_data.get("interests", {}).get("conferences", []),
                "organizations": profile_data.get("interests", {}).get("organizations", [])
            },
            
            "professional_experience": profile_data.get("professional_experience", []),
            
            "resume": {
                "uploaded": False,
                "file_id": None,
                "filename": None,
                "upload_date": None,
                "processed": False
            },
            
            "llm_parsed_backup": profile_data.get("llm_parsed_backup", None)
        }
        
        return profile_doc

def validate_profile_data(data: Dict[str, Any]) -> Dict[str, list]:
    """Validate profile data and return any errors"""
    errors = {}
    
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
    
    email = data.get("personal_info", {}).get("email", "")
    if email and "@" not in email:
        if "format" not in errors:
            errors["format"] = []
        errors["format"].append("Invalid email format")
    
    return errors

class AuthHelper:
    """Helper class for authentication operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storing"""
        return generate_password_hash(password)
    
    @staticmethod
    def check_password(password_hash: str, password: str) -> bool:
        """Check a hashed password against user input"""
        return check_password_hash(password_hash, password)