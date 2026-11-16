"""Schemas Pydantic cho danh mục meta và tin tuyển dụng nhà tuyển dụng."""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


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
    company_name: str
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


class HomeStatsOut(BaseModel):
    total_published_jobs: int
    today_new_jobs: int
    total_companies: int

