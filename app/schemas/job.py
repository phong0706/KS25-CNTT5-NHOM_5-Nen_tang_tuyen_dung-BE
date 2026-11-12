from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


JobStatus = Literal["DRAFT", "PENDING", "OPEN", "HIDDEN", "CLOSED", "REJECTED"]
JobType = Literal["FULLTIME", "PARTTIME", "INTERN", "REMOTE"]


class JobSkillInput(BaseModel):
    skill_id: int = Field(gt=0)
    is_required: bool = True


class JobFields(BaseModel):
    title: str = Field(min_length=5, max_length=255)
    industry_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    job_type: JobType = "FULLTIME"
    experience_level: str = Field(default="", max_length=50)
    is_negotiable: bool = False
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="VND", max_length=10)
    quantity: int = Field(default=1, ge=1)
    description: str
    requirements: str | None = None
    benefits: str | None = None
    deadline: datetime
    skills: list[JobSkillInput] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title không được để trống")
        return value.strip()

class JobCreate(JobFields):
    status: Literal["DRAFT", "PENDING", "OPEN"] = "DRAFT"
    # Chỉ ADMIN dùng để đăng tin thay mặt một công ty đã xác minh.
    company_id: int | None = Field(default=None, gt=0)


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=255)
    industry_id: int | None = Field(default=None, gt=0)
    location_id: int | None = Field(default=None, gt=0)
    job_type: JobType | None = None
    experience_level: str | None = Field(default=None, max_length=50)
    is_negotiable: bool | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
    quantity: int | None = Field(default=None, ge=1)
    description: str | None = None
    requirements: str | None = None
    benefits: str | None = None
    deadline: datetime | None = None
    skills: list[JobSkillInput] | None = None


class JobStatusUpdate(BaseModel):
    status: JobStatus


class JobSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    skill_id: int
    is_required: bool


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    posted_by: int
    title: str
    industry_id: int
    location_id: int
    job_type: str
    experience_level: str
    salary_min: Decimal | None
    salary_max: Decimal | None
    is_negotiable: bool
    currency: str
    quantity: int
    description: str
    requirements: str | None
    benefits: str | None
    deadline: datetime
    status: str
    views_count: int
    created_at: datetime | None
    updated_at: datetime | None
    job_skills: list[JobSkillOut]


class JobMutationResponse(BaseModel):
    statusCode: int
    message: str
    data: JobOut


class JobSearchOut(BaseModel):
    id: int
    title: str
    description: str | None
    company_name: str
    industry_name: str
    location_name: str
    deadline: datetime
    created_at: datetime


class SavedJobDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company_name: str
    industry_name: str
    location_name: str
    deadline: datetime
    saved_at: datetime
