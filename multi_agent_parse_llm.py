from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from pydantic_ai import Agent, Tool
from dateutil import parser as dateparser  # keep if you need date normalization later
import os
from dotenv import load_dotenv
import asyncio

from extract_text_from_pdf import extract_text_from_pdf

# -------------------------
# Env / API key
# -------------------------
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in environment. Please set it in your .env file.")

Model_Name="openai:gpt-4o-mini"  # or "anthropic:claude-2"
# -------------------------
# Schemas
# -------------------------
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
    startDate: Optional[str] = Field(None, description="ISO-like (YYYY-MM or YYYY)")
    endDate: Optional[str]   = Field(None, description="ISO-like (YYYY-MM or YYYY) or 'Present'")
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
    skillProficiency: SkillProf = "Intermediate"

class TechnicalSkillsModel(BaseModel):
    technical_skills: List[TechnicalSkillItem] = [] # default Intermediate

class SoftSkillsModel(BaseModel):
    soft_skills: List[str] = []

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

# Sub-models per worker
class ProfileInfoModel(BaseModel):
    profile_information: ProfileInfo

class CourseworkModel(BaseModel):
    coursework: List[CourseworkItem] = []
    past_academic_profile_text: Optional[str] = None

class ExperienceModel(BaseModel):
    professional_experience: List[ExperienceItem] = []

class ProjectsModel(BaseModel):
    projects: List[ProjectItem] = []

class LanguagesModel(BaseModel):
    languages: List[LanguageItem] = []

class ConferencesModel(BaseModel):
    conferences: List[ConferenceItem] = []

class TechSkillsModel(BaseModel):
    technical_skills: List[TechnicalSkillItem] = []
    soft_skills: List[str] = []

# -------------------------
# Prompts
# -------------------------
P_PROFILE = """
Extract ONLY the current academic profile (UNC Charlotte focus if present):
- full_name
- college-priority email
- academic_level (freshman/sophomore/junior/senior/graduate/PhD)
- program (e.g., Bachelor Of Arts, Master of Sciences)
- major (e.g., Computer Science)
If missing, leave null. Return ProfileInfoModel only.
"""

P_COURSEWORK = """
Extract coursework:
- For each course: {course_code?, course_title, course_status in {"In Progress","Completed"}}
- Also produce a free-text 'past_academic_profile_text' summarizing prior degrees/schools before current program.
Return CourseworkModel only.
"""

P_EXPERIENCE = """
Extract professional experience items:
- title, company, startDate, endDate ("Present" allowed), status in {"Past","Current Job"}, jobDescription.
Return ExperienceModel only.
"""

P_PROJECTS = """
Extract projects with {projectTitle, projectDescription}. Return ProjectsModel only.
"""

P_LANGS = """
Extract spoken languages with proficiency in {"Native","Beginner","Intermediate","Fluent"}; default to "Fluent".
Return LanguagesModel only.
"""

P_CONF = """
Extract conferences/activities: {conferenceTitle, title (attendant/volunteer/presenter/participant), year?}. Return ConferencesModel only.
"""

P_TECH = """
Extract ONLY technical skills with proficiency.
Return TechnicalSkillsModel only.

Rules:
- technical_skills: array of {skillName, skillProficiency in {"Beginner","Intermediate","Advanced"}}
- If proficiency is not stated, default to "Intermediate".
- Do not include soft skills here.
"""

P_SOFT = """
Extract ONLY soft skills (no proficiency). Return SoftSkillsModel only.
Examples of soft skills: Communication, Teamwork, Leadership, Problem-Solving,
Time Management, Adaptability, Collaboration, Critical Thinking, Mentorship.
Output should be an array of strings in 'soft_skills'.
"""

# -------------------------
# Sub-agents (use provider-prefixed model string)
# -------------------------
a_profile  = Agent(Model_Name, system_prompt=P_PROFILE,   output_type=ProfileInfoModel)
a_courses  = Agent(Model_Name, system_prompt=P_COURSEWORK, output_type=CourseworkModel)
a_exp      = Agent(Model_Name, system_prompt=P_EXPERIENCE, output_type=ExperienceModel)
a_projects = Agent(Model_Name, system_prompt=P_PROJECTS,   output_type=ProjectsModel)
a_langs    = Agent(Model_Name, system_prompt=P_LANGS,      output_type=LanguagesModel)
a_conf     = Agent(Model_Name, system_prompt=P_CONF,       output_type=ConferencesModel)
a_tech = Agent(Model_Name, system_prompt=P_TECH,  output_type=TechnicalSkillsModel)
a_soft = Agent(Model_Name, system_prompt=P_SOFT,  output_type=SoftSkillsModel)

# -------------------------
# Controller
# -------------------------
CTRL_PROMPT = """
You orchestrate specialized workers to parse resume text into a final structured object (ResumeModel).
For each section, call the appropriate tool. Merge results and return the full ResumeModel.

Rules:
- Do NOT invent facts. If something is missing, leave it empty/null.
- Prefer *.edu email if present.
- Defaults: language=Fluent if unspecified; skill=Intermediate if unspecified.
- Course status must be {"In Progress","Completed"}.
- Experience status must be {"Past","Current Job"}.
"""

# NOTE: Tool funcs are sync and call run_sync(...).output
@Tool
async def extract_profile(resume_text: str) -> ProfileInfoModel:
    result = await a_profile.run(resume_text)
    return result.output

@Tool
async def extract_coursework(resume_text: str) -> CourseworkModel:
    result = await a_courses.run(resume_text)
    return result.output

@Tool
async def extract_experience(resume_text: str) -> ExperienceModel:
    result = await a_exp.run(resume_text)
    return result.output

@Tool
async def extract_projects(resume_text: str) -> ProjectsModel:
    result = await a_projects.run(resume_text)
    return result.output

@Tool
async def extract_languages(resume_text: str) -> LanguagesModel:
    result = await a_langs.run(resume_text)
    return result.output

@Tool
async def extract_conferences(resume_text: str) -> ConferencesModel:
    result = await a_conf.run(resume_text)
    return result.output

@Tool
async def extract_techskills(resume_text: str) -> TechSkillsModel:
    result = await a_tech.run(resume_text)
    return result.output

controller = Agent(
    Model_Name,
    system_prompt=CTRL_PROMPT,
    tools=[extract_profile, extract_coursework, extract_experience,
           extract_projects, extract_languages, extract_conferences, extract_techskills],
    output_type=ResumeModel,
)

def parse_resume_text_multiagent_deterministic(resume_text: str) -> ResumeModel:
    prof    = a_profile.run_sync(resume_text).output               # ProfileInfoModel
    course  = a_courses.run_sync(resume_text).output               # CourseworkModel
    exp     = a_exp.run_sync(resume_text).output                   # ExperienceModel
    proj    = a_projects.run_sync(resume_text).output              # ProjectsModel
    langs   = a_langs.run_sync(resume_text).output                 # LanguagesModel
    confs   = a_conf.run_sync(resume_text).output                  # ConferencesModel
    tech    = a_tech.run_sync(resume_text).output                  # TechnicalSkillsModel
    soft    = a_soft.run_sync(resume_text).output                  # SoftSkillsModel

    merged = ResumeModel(
        profile_information=prof.profile_information,
        coursework=course.coursework,
        past_academic_profile_text=course.past_academic_profile_text,
        professional_experience=exp.professional_experience,
        projects=proj.projects,
        languages=langs.languages,
        conferences=confs.conferences,
        technical_skills=tech.technical_skills,     # ✅ proficiency kept
        soft_skills=soft.soft_skills,               # ✅ separate list preserved
    )
    return merged


async def parse_resume_text_multiagent(resume_text: str) -> ResumeModel:
    res = await controller.run(resume_text)
    return res.output

if __name__ == "__main__":
    pdf_path = "uploads/Full_TestCase.pdf"
    resume_text = extract_text_from_pdf(pdf_path)
    parsed = parse_resume_text_multiagent_deterministic(resume_text)
    print(parsed.model_dump_json(indent=2))