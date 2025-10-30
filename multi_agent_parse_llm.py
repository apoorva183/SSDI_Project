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

# -------------------------
# Schemas
# -------------------------
AcademicLevel = Literal["undergraduate","graduate","PhD"]
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
    past_academic_profile_text: Optional[str] = Field(
        None,
        description="Summary of all academic history prior to the current program"
    )
    previous_degrees: List[str] = Field(
        default_factory=list,
        description="List of previously completed degrees (e.g., 'Bachelor of Science in Biology, 2020')"
    )
    previous_institutions: List[str] = Field(
        default_factory=list,
        description="List of previously attended educational institutions"
    )
    graduation_years: List[int] = Field(
        default_factory=list,
        description="Graduation years for previous degrees"
    )

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
IMPORTANT: Extract ONLY if the information is explicitly present in the resume. If any field is missing or unclear, leave it null. Do NOT guess, infer, or invent any details. Return ProfileInfoModel only.
"""

P_PAST_COURSEWORK = """
Extract all academic history that occurred BEFORE the current program (current program is in year 2025):

- Include previous degrees earned (with completion years if available)
- Include previous institutions attended
- Include previous majors/minors
- Include relevant coursework from past programs
- Include academic honors or achievements from past education
- Include high school information if present

EXCLUDE:
- The current program (any program with graduation year 2025 or later)
- Any coursework or degree marked as 'in progress', 'present', or ending in 2025 or later

IMPORTANT: Only extract information that is explicitly stated in the resume. If a detail is not present, leave it empty or null. Do NOT guess, infer, or invent any information.

Return CourseworkModel with:
1. 'past_academic_profile_text': A comprehensive text summary of all past academic history
2. 'previous_degrees': Array of degree strings (e.g., ["Bachelor of Arts in Psychology, University of XYZ, 2018"])
3. 'previous_institutions': Array of institution names
4. 'graduation_years': Array of years for previous degrees

If no past academic history is found, return empty/null values.
"""

P_EXPERIENCE = """
Extract professional experience items:
- title, company, startDate, endDate ("Present" allowed), status in {"Past","Current Job"}, jobDescription.
IMPORTANT: Only extract information that is explicitly present in the resume. If any field is missing or unclear, leave it null. Do NOT guess, infer, or invent any details. Return ExperienceModel only.
"""

P_PROJECTS = """
Extract projects with {projectTitle, projectDescription}. 
IMPORTANT: Only extract projects that are explicitly mentioned in the resume. If a project or its description is missing, leave it null. Do NOT guess, infer, or invent any information. Return ProjectsModel only.
"""

P_LANGS = """
Extract spoken languages with proficiency in {"Native","Beginner","Intermediate","Fluent"}; default to "Fluent" ONLY if proficiency is explicitly not stated but language is present.
IMPORTANT: Only extract languages that are explicitly mentioned in the resume. If a language or its proficiency is missing, leave it null. Do NOT guess, infer, or invent any information. Return LanguagesModel only.
"""

P_CONF = """
Extract conferences/activities: {conferenceTitle, title (attendant/volunteer/presenter/participant), year?}.
IMPORTANT: Only extract conferences or activities that are explicitly mentioned in the resume. If any field is missing or unclear, leave it null. Do NOT guess, infer, or invent any information. Return ConferencesModel only.
"""

P_TECH = """
Extract ONLY technical skills with proficiency.
Return TechnicalSkillsModel only.

Rules:
- technical_skills: array of {skillName, skillProficiency in {"Beginner","Intermediate","Advanced"}}
- If proficiency is not stated but skill is present, default to "Intermediate".
- Do not include soft skills here.

IMPORTANT: Only extract technical skills that are explicitly mentioned in the resume. If a skill or its proficiency is missing, leave it null or use the default as above. Do NOT guess, infer, or invent any information.
"""

P_SOFT = """
Extract ONLY soft skills (no proficiency). Return SoftSkillsModel only.
Examples of soft skills: Communication, Teamwork, Leadership, Problem-Solving,
Time Management, Adaptability, Collaboration, Critical Thinking, Mentorship.
Output should be an array of strings in 'soft_skills'.

IMPORTANT: Only extract soft skills that are explicitly mentioned in the resume. If a soft skill is not present, do NOT guess, infer, or invent any information.
"""

# -------------------------
# Sub-agents (use provider-prefixed model string)
# -------------------------
a_profile  = Agent('openai:gpt-4o-mini', system_prompt=P_PROFILE,   output_type=ProfileInfoModel)
a_courses  = Agent('openai:gpt-4o-mini', system_prompt=P_PAST_COURSEWORK, output_type=CourseworkModel)
a_exp      = Agent('openai:gpt-4o-mini', system_prompt=P_EXPERIENCE, output_type=ExperienceModel)
a_projects = Agent('openai:gpt-4o-mini', system_prompt=P_PROJECTS,   output_type=ProjectsModel)
a_langs    = Agent('openai:gpt-4o-mini', system_prompt=P_LANGS,      output_type=LanguagesModel)
a_conf     = Agent('openai:gpt-4o-mini', system_prompt=P_CONF,       output_type=ConferencesModel)
a_tech = Agent('openai:gpt-4o-mini', system_prompt=P_TECH,  output_type=TechnicalSkillsModel)
a_soft = Agent('openai:gpt-4o-mini', system_prompt=P_SOFT,  output_type=SoftSkillsModel)

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
async def extract_past_coursework(resume_text: str) -> CourseworkModel:
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
    'openai:gpt-4o-mini',
    system_prompt=CTRL_PROMPT,
    tools=[extract_profile, extract_experience,
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
    pdf_path = "uploads/MOCK_RESUME.pdf"
    resume_text = extract_text_from_pdf(pdf_path)
    parsed = parse_resume_text_multiagent_deterministic(resume_text)
    print(parsed.model_dump_json(indent=2))