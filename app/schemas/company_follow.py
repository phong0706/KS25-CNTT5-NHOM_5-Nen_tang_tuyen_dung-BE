"""DTO cho API theo dõi công ty."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyFollowItemOut(BaseModel):
    id: int
    name: str
    logo: str | None = None
    industry: str | None = None
    location: str | None = None
    active_job_count: int
    followed_at: datetime


class CompanyFollowListData(BaseModel):
    items: list[CompanyFollowItemOut]


class CompanyFollowListMeta(BaseModel):
    page: int
    limit: int
    total: int


class CompanyFollowListOut(BaseModel):
    success: bool = True
    data: CompanyFollowListData
    message: str
    meta: CompanyFollowListMeta


class CompanyFollowStatusData(BaseModel):
    company_id: int
    is_following: bool
    follower_count: int


class CompanyFollowStatusOut(BaseModel):
    success: bool = True
    data: CompanyFollowStatusData
    message: str


class CompanyFollowMutationData(BaseModel):
    company_id: int
    is_following: bool


class CompanyFollowMutationOut(BaseModel):
    success: bool = True
    data: CompanyFollowMutationData
    message: str
