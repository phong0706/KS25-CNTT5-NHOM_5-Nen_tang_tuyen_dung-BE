"""Schemas cho API hồ sơ ứng viên."""
from pydantic import BaseModel, Field


class CompletionMissingItem(BaseModel):
    key: str
    label: str
    weight: int
    target_section: str


class ProfileCompletionOut(BaseModel):
    percent: int
    missing: list[CompletionMissingItem]


class ExperienceOut(BaseModel):
    id: int
    title: str
    company: str
    start_month: str
    end_month: str | None = None
    is_current: bool
    description: str | None = None

    model_config = {"from_attributes": True}


class EducationOut(BaseModel):
    id: int
    school: str
    major: str
    degree: str
    start_year: int
    end_year: int | None = None

    model_config = {"from_attributes": True}


class CandidateProfileOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None = None
    avatar_url: str | None = None
    headline: str | None = None
    birth_date: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    bio: str | None = None
    skills: list[str] = Field(default_factory=list)
    is_searchable: bool = True
    version: int = 1
    experiences: list[ExperienceOut] = Field(default_factory=list)
    educations: list[EducationOut] = Field(default_factory=list)
    completion: ProfileCompletionOut


class CandidateProfilePatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    headline: str | None = Field(default=None, max_length=200)
    birth_date: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=120)
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=500)
    is_searchable: bool | None = None
    version: int | None = None


class SkillsUpdateIn(BaseModel):
    skills: list[str] = Field(default_factory=list, max_length=30)
    version: int | None = None


class ExperienceIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(min_length=2, max_length=200)
    start_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    end_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    is_current: bool = False
    description: str | None = Field(default=None, max_length=2000)


class EducationIn(BaseModel):
    school: str = Field(min_length=2, max_length=200)
    major: str = Field(min_length=2, max_length=200)
    degree: str = Field(min_length=2, max_length=120)
    start_year: int = Field(ge=1970, le=2035)
    end_year: int | None = Field(default=None, ge=1970, le=2040)


