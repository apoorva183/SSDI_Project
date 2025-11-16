"""
Student Profile Similarity Matching System
Integrates with NinerMatch data model to find compatible students
"""

import math
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict

# Global matcher instance
student_matcher = None
matcher_db = None

def set_matcher_db(db_manager):
    """Initialize the global matcher with database connection"""
    global student_matcher, matcher_db
    matcher_db = db_manager
    if student_matcher is None:
        student_matcher = StudentMatcher(db_manager)
    else:
        student_matcher.db_manager = db_manager


class StudentMatcher:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        # Default feature weights - can be personalized per user
        self.default_weights = {
            'academic_courses': 0.30,      # Same courses - high weight for study groups
            'technical_skills': 0.25,      # Technical skill overlap
            'languages': 0.10,             # Language compatibility
            'academic_level': 0.10,        # Same year/level students
            'professional_experience': 0.10, # Professional experience overlap
            'major_program': 0.05,         # Same major/program
            'academic_interests': 0.05,    # Academic interests alignment (reduced)
            'personal_interests': 0.05     # Personal interests
        }
    
    def jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calculate Jaccard similarity between two sets"""
        try:
            if not set1 and not set2:
                return 1.0  # Both empty
            if not set1 or not set2:
                return 0.0  # One empty
            
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            return intersection / union if union > 0 else 0.0
        except Exception as e:
            print(f"Error in jaccard_similarity: {e}")
            print(f"Set1 type: {type(set1)}, Set2 type: {type(set2)}")
            return 0.0
    
    def skill_similarity_with_proficiency(self, skills1: List[Dict], skills2: List[Dict]) -> float:
        """
        Calculate similarity between technical skills considering proficiency levels
        Format: [{"skillName": "Python", "skillProficiency": "Advanced"}]
        """
        if not skills1 and not skills2:
            return 1.0
        if not skills1 or not skills2:
            return 0.0
        
        # Convert to dictionaries for easier lookup
        skills1_dict = {}
        for skill in skills1:
            if isinstance(skill, dict):
                skill_name = skill.get('skillName', skill.get('name', str(skill)))
                skill_prof = skill.get('skillProficiency', skill.get('proficiency', 'Intermediate'))
            else:
                skill_name = str(skill)
                skill_prof = 'Intermediate'
            skills1_dict[skill_name] = skill_prof
        
        skills2_dict = {}
        for skill in skills2:
            if isinstance(skill, dict):
                skill_name = skill.get('skillName', skill.get('name', str(skill)))
                skill_prof = skill.get('skillProficiency', skill.get('proficiency', 'Intermediate'))
            else:
                skill_name = str(skill)
                skill_prof = 'Intermediate'
            skills2_dict[skill_name] = skill_prof
        
        # Get common skills
        common_skills = set(skills1_dict.keys()).intersection(set(skills2_dict.keys()))
        all_skills = set(skills1_dict.keys()).union(set(skills2_dict.keys()))
        
        if not all_skills:
            return 0.0
        
        # Base Jaccard similarity
        base_similarity = len(common_skills) / len(all_skills)
        
        # Proficiency bonus for common skills
        proficiency_bonus = 0.0
        proficiency_values = {'Beginner': 1, 'Intermediate': 2, 'Advanced': 3}
        
        for skill in common_skills:
            prof1 = proficiency_values.get(skills1_dict[skill], 2)
            prof2 = proficiency_values.get(skills2_dict[skill], 2)
            # Bonus for similar proficiency levels
            prof_similarity = 1 - abs(prof1 - prof2) / 2.0
            proficiency_bonus += prof_similarity
        
        if common_skills:
            proficiency_bonus /= len(common_skills)
        
        # Weighted combination
        return 0.7 * base_similarity + 0.3 * proficiency_bonus
    
    def language_similarity(self, langs1: List[Dict], langs2: List[Dict]) -> float:
        """
        Calculate language similarity considering proficiency
        Format: [{"language": "Spanish", "languageProficiency": "Fluent"}]
        """
        if not langs1 and not langs2:
            return 1.0
        if not langs1 or not langs2:
            return 0.0
        
        # Extract language names safely
        lang_names1 = set()
        for lang in langs1:
            if isinstance(lang, dict):
                lang_names1.add(lang.get('language', lang.get('name', str(lang))))
            else:
                lang_names1.add(str(lang))
        
        lang_names2 = set()
        for lang in langs2:
            if isinstance(lang, dict):
                lang_names2.add(lang.get('language', lang.get('name', str(lang))))
            else:
                lang_names2.add(str(lang))
        
        return self.jaccard_similarity(lang_names1, lang_names2)
    
    def academic_level_similarity(self, level1: str, level2: str) -> float:
        """Calculate similarity between academic levels"""
        if not level1 or not level2:
            return 0.0
        
        if level1 == level2:
            return 1.0
        
        # Define level hierarchies for partial matches
        undergrad_levels = {'freshman', 'sophomore', 'junior', 'senior'}
        grad_levels = {'graduate', 'masters', 'phd'}
        
        level1_lower = level1.lower()
        level2_lower = level2.lower()
        
        # Same category gets partial credit
        if (level1_lower in undergrad_levels and level2_lower in undergrad_levels) or \
           (level1_lower in grad_levels and level2_lower in grad_levels):
            return 0.5
        
        return 0.0
    
    def extract_experience_summary(self, experiences: List[Dict]) -> set:
        """
        Extract key terms from professional experience for similarity matching
        Creates a summary from job titles and company names
        """
        if not experiences:
            return set()
        
        summary_terms = set()
        
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
                
            # Extract and process job title
            title = exp.get('title', '').strip()
            if title:
                # Split title into meaningful terms
                title_words = title.lower().replace('-', ' ').replace('_', ' ').split()
                # Filter out common words and keep meaningful terms
                meaningful_words = [word for word in title_words 
                                  if len(word) > 2 and word not in {'and', 'the', 'for', 'with', 'intern', 'junior', 'senior'}]
                summary_terms.update(meaningful_words)
            
            # Extract industry/company type from company name
            company = exp.get('company', '').strip()
            if company:
                company_words = company.lower().replace('-', ' ').replace('_', ' ').split()
                # Add company name terms (useful for industry matching)
                meaningful_company_words = [word for word in company_words 
                                          if len(word) > 3 and word not in {'inc', 'corp', 'ltd', 'llc', 'company', 'group'}]
                summary_terms.update(meaningful_company_words[:2])  # Limit to 2 most relevant terms
        
        return summary_terms
    
    def professional_experience_similarity(self, exp1: List[Dict], exp2: List[Dict]) -> float:
        """
        Calculate similarity between professional experiences
        Based on job titles, companies, and industry overlap
        """
        if not exp1 and not exp2:
            return 1.0  # Both have no experience
        if not exp1 or not exp2:
            return 0.3  # One has experience, other doesn't - partial credit
        
        # Extract experience summaries
        summary1 = self.extract_experience_summary(exp1)
        summary2 = self.extract_experience_summary(exp2)
        
        if not summary1 and not summary2:
            return 1.0  # Both have empty summaries
        if not summary1 or not summary2:
            return 0.2  # One empty, other not
        
        # Calculate Jaccard similarity on experience terms
        base_similarity = self.jaccard_similarity(summary1, summary2)
        
        # Bonus for having similar number of experiences (career stage alignment)
        exp_count_diff = abs(len(exp1) - len(exp2))
        count_bonus = max(0, 0.2 - (exp_count_diff * 0.05))  # Up to 0.2 bonus, reduced by difference
        
        final_similarity = min(1.0, base_similarity + count_bonus)
        return final_similarity
    
    def calculate_similarity(self, profile1: Dict[str, Any], profile2: Dict[str, Any], 
                           custom_weights: Dict[str, float] = None) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate overall similarity between two student profiles
        Returns: (similarity_score, detailed_breakdown)
        """
        print(f"🧮 ML Algorithm: Calculating similarity between profiles...")
        weights = custom_weights or self.default_weights
        similarities = {}
        commonalities = []
        
        # 1. Academic Courses Similarity
        courses1_raw = profile1.get('academic', {}).get('courses', [])
        courses2_raw = profile2.get('academic', {}).get('courses', [])
        
        # Ensure courses are strings (handle both string and dict formats)
        courses1 = set()
        for course in courses1_raw:
            if isinstance(course, dict):
                courses1.add(course.get('name', course.get('course_name', str(course))))
            else:
                courses1.add(str(course))
        
        courses2 = set()
        for course in courses2_raw:
            if isinstance(course, dict):
                courses2.add(course.get('name', course.get('course_name', str(course))))
            else:
                courses2.add(str(course))
        
        course_sim = self.jaccard_similarity(courses1, courses2)
        similarities['academic_courses'] = course_sim
        
        # Track common courses
        common_courses = courses1.intersection(courses2)
        if common_courses:
            commonalities.append(f"Both taking: {', '.join(list(common_courses)[:3])}")
        
        # 2. Technical Skills Similarity  
        tech_skills1 = profile1.get('skills', {}).get('technical', [])
        tech_skills2 = profile2.get('skills', {}).get('technical', [])
        tech_sim = self.skill_similarity_with_proficiency(tech_skills1, tech_skills2)
        similarities['technical_skills'] = tech_sim
        
        # Track common skills
        if isinstance(tech_skills1, list) and isinstance(tech_skills2, list):
            skills1_names = set()
            for skill in tech_skills1:
                if isinstance(skill, dict):
                    skills1_names.add(skill.get('skillName', skill.get('name', str(skill))))
                else:
                    skills1_names.add(str(skill))
            
            skills2_names = set()
            for skill in tech_skills2:
                if isinstance(skill, dict):
                    skills2_names.add(skill.get('skillName', skill.get('name', str(skill))))
                else:
                    skills2_names.add(str(skill))
            
            common_skills = skills1_names.intersection(skills2_names)
            if common_skills:
                commonalities.append(f"Shared skills: {', '.join(list(common_skills)[:3])}")
        
        # 3. Academic Interests
        interests1_raw = profile1.get('interests', {}).get('academic', [])
        interests2_raw = profile2.get('interests', {}).get('academic', [])
        
        # Ensure interests are strings
        interests1 = set()
        for interest in interests1_raw:
            if isinstance(interest, dict):
                interests1.add(interest.get('name', str(interest)))
            else:
                interests1.add(str(interest))
        
        interests2 = set()
        for interest in interests2_raw:
            if isinstance(interest, dict):
                interests2.add(interest.get('name', str(interest)))
            else:
                interests2.add(str(interest))
        
        interest_sim = self.jaccard_similarity(interests1, interests2)
        similarities['academic_interests'] = interest_sim
        
        common_interests = interests1.intersection(interests2)
        if common_interests:
            commonalities.append(f"Common interests: {', '.join(list(common_interests)[:2])}")
        
        # 4. Languages
        langs1 = profile1.get('background', {}).get('languages', [])
        langs2 = profile2.get('background', {}).get('languages', [])
        lang_sim = self.language_similarity(langs1, langs2)
        similarities['languages'] = lang_sim
        
        # Track common languages
        if isinstance(langs1, list) and isinstance(langs2, list):
            lang_names1 = set()
            for lang in langs1:
                if isinstance(lang, dict):
                    lang_names1.add(lang.get('language', lang.get('name', str(lang))))
                else:
                    lang_names1.add(str(lang))
            
            lang_names2 = set()
            for lang in langs2:
                if isinstance(lang, dict):
                    lang_names2.add(lang.get('language', lang.get('name', str(lang))))
                else:
                    lang_names2.add(str(lang))
            
            common_langs = lang_names1.intersection(lang_names2)
            if common_langs:
                commonalities.append(f"Both speak: {', '.join(common_langs)}")
        
        # 5. Academic Level
        level1 = profile1.get('personal_info', {}).get('year', '')
        level2 = profile2.get('personal_info', {}).get('year', '')
        level_sim = self.academic_level_similarity(level1, level2)
        similarities['academic_level'] = level_sim
        
        if level1 == level2 and level1:
            commonalities.append(f"Both are {level1} students")
        
        # 6. Major/Program Similarity
        major1 = profile1.get('personal_info', {}).get('major', '').lower()
        major2 = profile2.get('personal_info', {}).get('major', '').lower()
        program1 = profile1.get('personal_info', {}).get('program', '').lower()
        program2 = profile2.get('personal_info', {}).get('program', '').lower()
        
        major_sim = 1.0 if major1 and major1 == major2 else 0.0
        program_sim = 1.0 if program1 and program1 == program2 else 0.0
        major_program_sim = max(major_sim, program_sim * 0.8)  # Program match worth 80% of major match
        similarities['major_program'] = major_program_sim
        
        if major1 == major2 and major1:
            commonalities.append(f"Both studying {major1.title()}")
        
        # 7. Professional Experience Similarity
        exp1 = profile1.get('professional_experience', [])
        exp2 = profile2.get('professional_experience', [])
        exp_sim = self.professional_experience_similarity(exp1, exp2)
        similarities['professional_experience'] = exp_sim
        
        # Track common experience areas
        if exp1 and exp2:
            exp_summary1 = self.extract_experience_summary(exp1)
            exp_summary2 = self.extract_experience_summary(exp2)
            common_exp = exp_summary1.intersection(exp_summary2)
            if common_exp:
                commonalities.append(f"Similar experience: {', '.join(list(common_exp)[:2])}")
        
        # 8. Personal Interests
        personal1_raw = profile1.get('interests', {}).get('personal', [])
        personal2_raw = profile2.get('interests', {}).get('personal', [])
        
        # Ensure personal interests are strings
        personal1 = set()
        for interest in personal1_raw:
            if isinstance(interest, dict):
                personal1.add(interest.get('name', str(interest)))
            else:
                personal1.add(str(interest))
        
        personal2 = set()
        for interest in personal2_raw:
            if isinstance(interest, dict):
                personal2.add(interest.get('name', str(interest)))
            else:
                personal2.add(str(interest))
        
        personal_sim = self.jaccard_similarity(personal1, personal2)
        similarities['personal_interests'] = personal_sim
        
        # Calculate weighted overall similarity
        overall_similarity = sum(
            similarities[feature] * weights.get(feature, 0) 
            for feature in similarities
        )
        
        # Ensure score is between 0 and 1
        overall_similarity = max(0.0, min(1.0, overall_similarity))
        
        # Detailed breakdown for debugging and display
        breakdown = {
            'overall_score': overall_similarity,
            'individual_scores': similarities,
            'weights_used': weights,
            'commonalities': commonalities,
            'match_level': self._get_match_level(overall_similarity)
        }
        
        return overall_similarity, breakdown
    
    def _get_match_level(self, score: float) -> str:
        """Convert numerical score to descriptive match level"""
        if score >= 0.8:
            return "Excellent Match"
        elif score >= 0.65:
            return "Great Match" 
        elif score >= 0.5:
            return "Good Match"
        elif score >= 0.35:
            return "Moderate Match"
        else:
            return "Low Match"
    
    def find_matches_for_user(self, user_profile: Dict[str, Any], 
                            exclude_user_id: str = None, 
                            limit: int = 10,
                            min_similarity: float = 0.2) -> List[Dict[str, Any]]:
        """
        Find and rank potential matches for a user
        """
        if not self.db_manager or self.db_manager.db is None:
            return []
        
        try:
            # Get all active profiles except the current user
            query = {"status": "active"}
            
            # Build exclusion criteria - exclude by multiple possible identifiers
            exclude_conditions = []
            
            if exclude_user_id:
                exclude_conditions.append({"profile_id": {"$ne": exclude_user_id}})
            
            # Always exclude by email to prevent self-matching
            user_email = user_profile.get('personal_info', {}).get('email')
            if user_email:
                exclude_conditions.append({"personal_info.email": {"$ne": user_email}})
            
            # Also exclude by _id if available
            user_id = user_profile.get('_id')
            if user_id:
                exclude_conditions.append({"_id": {"$ne": user_id}})
            
            # Apply exclusion conditions
            if exclude_conditions:
                query["$and"] = exclude_conditions
            
            all_profiles = list(self.db_manager.db.profiles.find(query))
            matches = []
            
            for profile in all_profiles:
                # Double-check: never match with self by email
                if (profile.get('personal_info', {}).get('email') == user_email):
                    continue
                    
                similarity_score, breakdown = self.calculate_similarity(user_profile, profile)
                
                if similarity_score >= min_similarity:
                    match_info = {
                        'profile_id': profile.get('profile_id'),
                        'user_id': str(profile.get('_id')),
                        'personal_info': profile.get('personal_info', {}),
                        'academic': profile.get('academic', {}),
                        'skills': profile.get('skills', {}),
                        'interests': profile.get('interests', {}),
                        'past_academic_profile_text': profile.get('past_academic_profile_text', ''),
                        'similarity_score': similarity_score,
                        'match_level': breakdown['match_level'],
                        'commonalities': breakdown['commonalities'],
                        'created_at': profile.get('created_at')
                    }
                    matches.append(match_info)
            
            # Sort by similarity score (highest first)
            matches.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return matches[:limit]
            
        except Exception as e:
            print(f"Error finding matches: {e}")
            return []
    
    def update_user_preferences(self, user_id: str, feedback_data: List[Tuple[str, int]]):
        """
        Update user's preference weights based on swipe feedback
        feedback_data: List of (feature_name, feedback_score) where feedback_score is 1 for like, -1 for dislike
        """
        try:
            # Get current user preferences or use defaults
            user_prefs = self.db_manager.db.user_preferences.find_one({"user_id": user_id})
            
            if not user_prefs:
                user_prefs = {
                    "user_id": user_id,
                    "weights": self.default_weights.copy(),
                    "created_at": datetime.utcnow(),
                    "feedback_count": 0
                }
            
            weights = user_prefs.get("weights", self.default_weights.copy())
            
            # Update weights based on feedback
            learning_rate = 0.05  # How fast to adapt
            
            for feature, feedback in feedback_data:
                if feature in weights:
                    # Positive feedback increases weight, negative decreases
                    adjustment = learning_rate * feedback
                    weights[feature] = max(0.0, min(1.0, weights[feature] + adjustment))
            
            # Normalize weights to sum to 1
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v/total_weight for k, v in weights.items()}
            
            # Update in database
            user_prefs["weights"] = weights
            user_prefs["updated_at"] = datetime.utcnow()
            user_prefs["feedback_count"] = user_prefs.get("feedback_count", 0) + len(feedback_data)
            
            self.db_manager.db.user_preferences.replace_one(
                {"user_id": user_id}, 
                user_prefs, 
                upsert=True
            )
            
            return weights
            
        except Exception as e:
            print(f"Error updating user preferences: {e}")
            return self.default_weights

# Global matcher instance
student_matcher = StudentMatcher()

def set_matcher_db(db_manager):
    """Set database manager for the global matcher instance"""
    student_matcher.db_manager = db_manager