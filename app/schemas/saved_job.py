"""Schema cho tính năng Lưu tin tuyển dụng (SavedJob)."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SavedJobCreate(BaseModel):
    """Dữ liệu gửi lên khi ứng viên lưu tin tuyển dụng.

    Nếu ứng viên đã đăng nhập (có Bearer token), hệ thống tự động lấy
    candidate_profile_id từ tài khoản đang đăng nhập nếu không truyền.
    """

    candidate_profile_id: int | None = Field(
        default=None,
        gt=0,
        examples=[1],
        description="ID hồ sơ ứng viên (tự động lấy từ JWT nếu đã đăng nhập)",
    )
    job_id: int = Field(gt=0, examples=[1], description="ID tin tuyển dụng cần lưu")


class SavedJobOut(BaseModel):
    """Dữ liệu trả về sau khi lưu tin tuyển dụng."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_profile_id: int
    job_id: int
    saved_at: datetime


class SavedJobDetailOut(BaseModel):
    """Thông tin chi tiết của tin tuyển dụng đã lưu (kèm công ty, ngành, địa điểm)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    title: str
    company_id: int | None = None
    company_name: str
    company_logo: str | None = None
    industry_id: int | None = None
    industry_name: str
    location_id: int | None = None
    location_name: str
    job_type: str | None = None
    experience_level: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    is_negotiable: bool = False
    currency: str = "VND"
    deadline: datetime
    saved_at: datetime