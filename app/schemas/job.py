"""Schemas Pydantic cho danh mục meta, tin tuyển dụng (Job) và Tìm kiếm / Phân trang."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.saved_job import SavedJobDetailOut


# ===========================================================================
# PHẦN 1: SCHEMAS DANH MỤC META & EMPLOYER / PUBLIC JOBS (feat/T3D36B4)
# ===========================================================================


class MetaOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    job_count: int = 0


class MetaCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    icon: str
    job_count: int = 0


class MetaSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    usage_count: int
    job_count: int = 0


class AllowedActionOut(BaseModel):
    key: str
    label: str
    tone: str = "default"


class JobTabOut(BaseModel):
    key: str
    label: str
    count: int


class JobPaginationOut(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class JobListItemOut(BaseModel):
    id: int
    title: str
    level: str | None = None
    work_type: str | None = None
    location: str | None = None
    quantity: int = 1
    deadline: date | None = None
    status: str
    status_label: str
    status_tone: str
    applicants_count: int = 0
    new_applicants_count: int = 0
    views_count: int = 0
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[AllowedActionOut] = Field(default_factory=list)


class EmployerJobsListOut(BaseModel):
    items: list[JobListItemOut]
    tabs: list[JobTabOut]
    counts: dict[str, int]
    pagination: JobPaginationOut
    server_time: datetime


class JobStatusPatchIn(BaseModel):
    action: str = Field(..., min_length=1, max_length=32)


class JobActionResultOut(BaseModel):
    id: int
    status: str
    status_label: str
    status_tone: str
    undo_action: str | None = None
    message: str


class JobDuplicateOut(BaseModel):
    id: int
    title: str
    status: str
    message: str


class JobDeleteOut(BaseModel):
    id: int
    message: str


class JobPayloadIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    work_type: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=1, le=999)
    deadline: date | None = None
    description: str | None = None
    requirements: str | None = None
    skills: list[str] = Field(default_factory=list, max_length=15)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    is_salary_negotiable: bool = False
    benefits: list[str] = Field(default_factory=list, max_length=30)
    status: str = Field(default="draft", pattern="^(draft|pending)$")


class JobDetailOut(BaseModel):
    id: int
    title: str
    level: str | None = None
    work_type: str | None = None
    location: str | None = None
    quantity: int = 1
    deadline: date | None = None
    description: str | None = None
    requirements: str | None = None
    skills: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    is_salary_negotiable: bool = False
    benefits: list[str] = Field(default_factory=list)
    status: str
    status_label: str
    status_tone: str
    views_count: int = 0
    company_name: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    server_time: datetime


class BulkJobActionIn(BaseModel):
    job_ids: list[int] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern="^(hide|close|delete)$")


class BulkJobActionOut(BaseModel):
    processed: int
    skipped: int
    message: str


class PublicJobCardOut(BaseModel):
    id: int
    title: str
    company_id: int | None = None
    company_slug: str | None = None
    company_name: str
    company_logo: str | None = None
    company_logo_2x: str | None = None
    location: str | None = None
    location_slug: str | None = None
    level: str | None = None
    level_slug: str | None = None
    work_type: str | None = None
    work_type_slug: str | None = None
    category: str | None = None
    category_slug: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    is_salary_negotiable: bool = False
    skills: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    created_at: datetime
    is_saved: bool = False
    is_expired: bool = False
    deadline: date | None = None
    match_score: int | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    match_reason: str | None = None
    salary_insight: str | None = None
    salary_insight_sample_size: int | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def validate_skills_list(cls, v):
        from app.services.skills_normalizer import normalize_skills
        return normalize_skills(v)


class CandidateProfileSummaryOut(BaseModel):
    skills_count: int = 0
    skills: list[str] = Field(default_factory=list)
    level: str | None = None
    location: str | None = None
    work_type: str | None = None
    summary_text: str = ""


class RecommendedJobsOut(BaseModel):
    has_skills: bool = True
    profile: CandidateProfileSummaryOut = Field(default_factory=CandidateProfileSummaryOut)
    items: list[PublicJobCardOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0
    message: str | None = None


class SavedJobsListOut(BaseModel):
    items: list[PublicJobCardOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0


class FacetItemOut(BaseModel):
    value: str
    label: str
    count: int


class PublicJobsFacetsOut(BaseModel):
    location: list[FacetItemOut] = Field(default_factory=list)
    level: list[FacetItemOut] = Field(default_factory=list)
    type: list[FacetItemOut] = Field(default_factory=list)
    category: list[FacetItemOut] = Field(default_factory=list)


class PublicJobsSearchOut(BaseModel):
    items: list[PublicJobCardOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    facets: PublicJobsFacetsOut


class FeaturedCompanyOut(BaseModel):
    id: int
    name: str
    slug: str | None = None
    job_count: int
    logo_url: str | None = None
    logo_url_2x: str | None = None
    logo_version: int = 1


class HomeStatsOut(BaseModel):
    total_published_jobs: int
    today_new_jobs: int
    total_companies: int
    weekly_new_jobs: int = 0
    salary_median: int = 0
    total_skills: int = 0


# ===========================================================================
# PHẦN 2: SCHEMAS MODULE JOB & TÌM KIẾM / PHÂN TRANG (develop)
# ===========================================================================


JobStatus = Literal["DRAFT", "PENDING", "OPEN", "HIDDEN", "CLOSED", "REJECTED"]
JobType = Literal["FULLTIME", "PARTTIME", "INTERN", "REMOTE"]
JobSortBy = Literal["newest", "salary_desc", "salary_asc"]


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
    job_skills: list[JobSkillOut] = Field(default_factory=list)


class JobMutationResponse(BaseModel):
    statusCode: int
    message: str
    data: JobOut


class JobSearchOut(BaseModel):
    """Thông tin 1 tin tuyển dụng trong kết quả tìm kiếm."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    company_id: int | None = None
    company_name: str
    company_logo: str | None = None
    company_logo_2x: str | None = None
    industry_id: int | None = None
    industry_name: str
    location_id: int | None = None
    location_name: str
    job_type: str = "FULLTIME"
    experience_level: str = ""
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    is_negotiable: bool = False
    currency: str = "VND"
    skills: list[str] = Field(default_factory=list)
    deadline: datetime
    created_at: datetime
    is_saved: bool = False


class JobSearchPageOut(BaseModel):
    """Kết quả tìm kiếm việc làm có phân trang."""

    items: list[JobSearchOut]
    total: int
    page: int
    page_size: int
    total_pages: int


__all__ = [
    "MetaOptionOut",
    "MetaCategoryOut",
    "MetaSkillOut",
    "AllowedActionOut",
    "JobTabOut",
    "JobPaginationOut",
    "JobListItemOut",
    "EmployerJobsListOut",
    "JobStatusPatchIn",
    "JobActionResultOut",
    "JobDuplicateOut",
    "JobDeleteOut",
    "JobPayloadIn",
    "JobDetailOut",
    "BulkJobActionIn",
    "BulkJobActionOut",
    "PublicJobCardOut",
    "CandidateProfileSummaryOut",
    "RecommendedJobsOut",
    "SavedJobsListOut",
    "FacetItemOut",
    "PublicJobsFacetsOut",
    "PublicJobsSearchOut",
    "FeaturedCompanyOut",
    "HomeStatsOut",
    "JobStatus",
    "JobType",
    "JobSortBy",
    "JobSkillInput",
    "JobFields",
    "JobCreate",
    "JobUpdate",
    "JobStatusUpdate",
    "JobSkillOut",
    "JobOut",
    "JobMutationResponse",
    "JobSearchOut",
    "JobSearchPageOut",
    "SavedJobDetailOut",
]