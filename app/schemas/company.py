"""Schema cho bảng companies."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.job import PublicJobCardOut


class CompanyOut(BaseModel):
    """Thông tin công ty trả về."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str | None = None
    employer_id: int
    is_draft: bool
    logo_url: str | None = None
    cover_url: str | None = None
    description: str | None = None
    industry_id: int | None = None
    industry_name: str | None = None
    size: str | None = None
    website: str | None = None
    address: str | None = None
    job_count: int = 0
    created_at: datetime | None = None


class CompanyListOut(BaseModel):
    items: list[CompanyOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class CompanyDetailOut(CompanyOut):
    jobs: list[PublicJobCardOut] = Field(default_factory=list)
    is_following: bool = Field(default=False, serialization_alias="isFollowing")
    follower_count: int = Field(default=0, serialization_alias="followerCount")
