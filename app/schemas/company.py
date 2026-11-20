"""Schema cho API Công ty công khai (/api/companies*) và phản hồi tương thích nội bộ."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.job import PublicJobCardOut


class CompanyIndustryOut(BaseModel):
    slug: str
    name: str


class CompanySalaryRangeOut(BaseModel):
    min: int
    max: int


class CompanyDetailSalaryOut(BaseModel):
    min: int
    max: int
    sample_size: int


class CompanyFacetItemOut(BaseModel):
    value: str
    label: str
    count: int


class CompanyFacetsOut(BaseModel):
    industry: list[CompanyFacetItemOut] = Field(default_factory=list)
    location: list[CompanyFacetItemOut] = Field(default_factory=list)
    size: list[CompanyFacetItemOut] = Field(default_factory=list)


class CompanyJobsFacetsOut(BaseModel):
    location: list[CompanyFacetItemOut] = Field(default_factory=list)
    level: list[CompanyFacetItemOut] = Field(default_factory=list)


class CompanyTopSkillOut(BaseModel):
    slug: str
    name: str
    count: int


class PublicCompanyCardOut(BaseModel):
    slug: str
    name: str
    logo_url: str | None = None
    logo_url_2x: str | None = None
    industry: CompanyIndustryOut | None = None
    location: str | None = None
    size_range: str | None = None
    is_verified: bool = False
    open_jobs: int = 0
    salary: CompanySalaryRangeOut | None = None
    top_skills: list[str] = Field(default_factory=list)
    latest_job_at: datetime | None = None


class PublicCompanyListOut(BaseModel):
    items: list[PublicCompanyCardOut]
    total: int
    page: int
    page_size: int
    facets: CompanyFacetsOut
    hiring_total: int


class PublicCompanyDetailOut(BaseModel):
    slug: str
    name: str
    tagline: str | None = None
    description: str | None = None
    logo_url: str | None = None
    logo_url_2x: str | None = None
    cover_url: str | None = None
    industry: CompanyIndustryOut | None = None
    location: str | None = None
    address: str | None = None
    size_range: str | None = None
    founded_year: int | None = None
    website: str | None = None
    is_verified: bool = False
    updated_at: datetime | None = None
    open_jobs: int = 0
    salary_range: CompanyDetailSalaryOut | None = None
    latest_job_at: datetime | None = None
    top_skills: list[CompanyTopSkillOut] = Field(default_factory=list)
    similar: list[PublicCompanyCardOut] = Field(default_factory=list)


class PublicCompanyJobsOut(BaseModel):
    items: list[PublicJobCardOut]
    total: int
    page: int
    page_size: int
    facets: CompanyJobsFacetsOut


class CompanyOut(BaseModel):
    """Thông tin công ty tương thích route nội bộ (my-company / toggle-approval)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str | None = None
    employer_id: int
    is_draft: bool
    logo_url: str | None = None
    logo_url_2x: str | None = None
    cover_url: str | None = None
    description: str | None = None
    industry_id: int | None = None
    industry_name: str | None = None
    size: str | None = None
    website: str | None = None
    address: str | None = None
    job_count: int = 0
    created_at: datetime | None = None
