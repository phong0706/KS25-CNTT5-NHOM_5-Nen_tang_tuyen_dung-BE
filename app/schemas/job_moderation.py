"""Schemas cho luồng duyệt tin tuyển dụng của Admin và Employer (<= 75 dòng)."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class JobModerationActionIn(BaseModel):
    version: int = Field(..., description="Phiên bản hiện tại của tin để chống xung đột.")


class JobRejectActionIn(BaseModel):
    version: int = Field(..., description="Phiên bản hiện tại của tin.")
    reason: str = Field(..., min_length=10, max_length=1000, description="Lý do từ chối tin.")


class AdminJobDeleteIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000, description="Lý do xóa tin tuyển dụng.")


class JobModerationOut(BaseModel):
    id: int
    title: str
    status: str
    version: int
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminJobListItemOut(BaseModel):
    id: int
    title: str
    company_name: str
    employer_email: str
    employer_name: Optional[str] = None
    status: str
    version: int
    deadline: Optional[date] = None
    created_at: datetime


class AdminJobDetailOut(BaseModel):
    id: int
    title: str
    company_name: str
    employer_email: str
    employer_name: Optional[str] = None
    status: str
    version: int
    location: Optional[str] = None
    work_type: Optional[str] = None
    level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    is_salary_negotiable: bool = False
    deadline: Optional[date] = None
    skills: Optional[list[str]] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime
    published_at: Optional[datetime] = None


class AdminJobsListOut(BaseModel):
    items: list[AdminJobListItemOut]
    total: int
    counts: dict[str, int]
