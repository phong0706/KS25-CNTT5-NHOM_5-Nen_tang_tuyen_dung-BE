"""Schemas cho API theo dõi công ty."""
from datetime import datetime

from pydantic import BaseModel


class FollowedCompanyOut(BaseModel):
    id: int
    name: str
    slug: str | None = None
    logo: str | None = None
    tagline: str | None = None
    followed_at: datetime
    active_jobs_count: int


class FollowedCompaniesListOut(BaseModel):
    items: list[FollowedCompanyOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class CompanyFollowResultOut(BaseModel):
    company_id: int
    is_following: bool
    message: str
