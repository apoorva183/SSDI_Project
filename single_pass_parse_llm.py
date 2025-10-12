# pip install pydantic pydantic-ai openai python-dotenv python-dateutil
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, constr
from pydantic_ai import Agent
from datetime import date
from dateutil import parser as dateparser
import re
from extract_text_from_pdf import extract_text_from_pdf

import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic_ai.models.openai import OpenAIModel

# Load .env file
load_dotenv()

# Access your API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment. Please set it in your .env file.")

# Initialize OpenAI client
openai_model = OpenAIModel(
    model="gpt-4o-mini",
    api_key=OPENAI_API_KEY
)

# =========================
# 1) Pydantic data models
# =========================

AcademicLevel = Literal["freshman","sophomore","junior","senior","graduate","PhD"]
CourseStatus  = Literal["In Progress","Completed"]
JobStatus     = Literal["Past","Current Job"]
LangProf      = Literal["Native","Beginner","Intermediate","Fluent"]
SkillProf     = Literal["Beginner","Intermediate","Advanced"]

class ProfileInfo(BaseModel):
    full_name: str
    email: str = Field(..., description="Prefer college email; if none, use any available")
    academic_level: Optional[AcademicLevel] = None
    program: Optional[str] = Field(None, description="e.g., Bachelor of Arts, Master of Sciences")
    major: Optional[str]  = Field(None, description="e.g., Computer Science, Cybersecurity")

class CourseworkItem(BaseModel):
    course_code: Optional[str] = Field(None, description="e.g., ITCS 6112")
    course_title: str
    course_status: CourseStatus

class ExperienceItem(BaseModel):
    title: str
    company: str
    startDate: Optional[str] = Field(None, description="ISO-like (YYYY-MM or YYYY); parse from text if possible")
    endDate: Optional[str]   = Field(None, description="ISO-like (YYYY-MM or YYYY); ‘Present’ allowed")
    status: JobStatus
    jobDescription: str

class ProjectItem(BaseModel):
    projectTitle: str
    projectDescription: str

class LanguageItem(BaseModel):
    language: str
    languageProficiency: LangProf = "Fluent"  # default Fluent

class ConferenceItem(BaseModel):
    conferenceTitle: str
    title: Optional[str] = Field(None, description="attendant/volunteer/presenter/participant/etc.")
    year: Optional[int]  = None

class TechnicalSkillItem(BaseModel):
    skillName: str
    skillProficiency: SkillProf = "Intermediate"  # default Intermediate

class ResumeModel(BaseModel):
    profile_information: ProfileInfo
    coursework: List[CourseworkItem] = []
    past_academic_profile_text: Optional[str] = None
    professional_experience: List[ExperienceItem] = []
    projects: List[ProjectItem] = []
    languages: List[LanguageItem] = []
    conferences: List[ConferenceItem] = []
    technical_skills: List[TechnicalSkillItem] = []
    soft_skills: List[str] = []


# =========================
# 2) Agent with strict instructions
# =========================

SYSTEM_PROMPT = """
You are a resume parser. You will receive plain text extracted from a PDF/DOCX resume.
Output MUST strictly follow the provided Pydantic schema (ResumeModel).
Follow these rules:

1) EMAIL: Prefer college email if present (e.g., *.edu). If none, use any available email.
2) ACADEMIC LEVEL: one of {freshman,sophomore,junior,senior,graduate,PhD}. If unclear, leave null.
3) PROGRAM: e.g., "Bachelor Of Arts", "Master of Sciences" (keep as written in resume).
4) MAJOR: e.g., "Computer Science", "Information Technology", "Cybersecurity".
5) COURSEWORK: Each item must have course_title; include course_code if present; course_status in {"In Progress","Completed"}.
6) PAST ACADEMIC PROFILE: Provide as free text (prior degrees/schools before current program).
7) EXPERIENCE: status is {"Past","Current Job"}; Dates should be "YYYY-MM" or "YYYY" if month is unknown. Allow "Present" for endDate if needed.
8) PROJECTS: title + short description.
9) LANGUAGES: Use proficiency in {"Native","Beginner","Intermediate","Fluent"}; default to "Fluent" if not stated.
10) CONFERENCES: conferenceTitle; role title (attendant/volunteer/presenter/participant etc.); year if stated.
11) TECHNICAL SKILLS: include proficiency {"Beginner","Intermediate","Advanced"}; default "Intermediate" if not stated.
12) SOFT SKILLS: array of strings.
13) If resume is missing something, leave the field empty/null (do not invent facts).
14) Return only data that fits the schema; be concise, structured, and honest about missing info.
"""

# Choose your OpenAI model via environment variables, e.g., OPENAI_API_KEY
agent = Agent(
    model = openai_model,                # or any JSON-capable model you prefer
    system_prompt=SYSTEM_PROMPT,
    result_type=ResumeModel,             # <-- hard contract
)

# =========================
# 3) Helper: light post-normalization (optional)
# =========================
def normalize_dates(exp: ExperienceItem) -> ExperienceItem:
    def norm(d: Optional[str]) -> Optional[str]:
        if not d: 
            return None
        if d.lower() in {"present","current"}:
            return "Present"
        try:
            dt = dateparser.parse(d, default=date(1900,1,1))
            # return YYYY-MM if month known, otherwise YYYY
            if dt.month:
                return f"{dt.year:04d}-{dt.month:02d}"
            return f"{dt.year:04d}"
        except Exception:
            return d
    exp.startDate = norm(exp.startDate)
    exp.endDate   = norm(exp.endDate)
    return exp

def postprocess(res: ResumeModel) -> ResumeModel:
    # Normalize experience dates gently
    res.professional_experience = [normalize_dates(e) for e in res.professional_experience]
    # Trim whitespace on strings
    for c in res.coursework:
        if c.course_code: c.course_code = c.course_code.strip()
        c.course_title = c.course_title.strip()
    return res

# =========================
# 4) Run on extracted text
# =========================
def parse_resume_text(resume_plain_text: str) -> ResumeModel:
    result = agent.run(resume_plain_text)
    data: ResumeModel = result.data  # already validated by Pydantic
    return postprocess(data)

# Usage:
if __name__ == "__main__":
    pdf_path = "uploads/Full_TestCase.pdf"
    text = extract_text_from_pdf(pdf_path)
    parsed = parse_resume_text(text)
    print(parsed.model_dump())
