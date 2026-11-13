"""Schema cho Application - Đơn ứng tuyển.

FastAPI dùng schema để tự kiểm tra dữ liệu: sai kiểu / thiếu trường -> trả lỗi 422.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStatus


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class ApplicationBase(BaseModel):
    """Base schema cho Application."""
    cv_id: int | None = Field(default=None, examples=[1])
    cover_letter: str | None = Field(default=None, examples=["Tôi rất mong muốn được làm việc tại công ty..."])


class ApplicationCreate(ApplicationBase):
    """Dữ liệu FE gửi lên khi ứng viên tạo đơn ứng tuyển mới."""
    job_id: int = Field(examples=[5])


class ApplicationUpdate(BaseModel):
    """Dữ liệu FE gửi lên khi cập nhật đơn ứng tuyển.
    
    Ứng viên có thể sửa cover_letter, cv_id hoặc withdraw (rút đơn).
    Nhà tuyển dụng có thể sửa status, employer_notes.
    """
    cv_id: int | None = None
    cover_letter: str | None = None
    status: ApplicationStatus | None = None
    employer_notes: str | None = None


class ApplicationOut(ApplicationBase):
    """Dữ liệu đơn ứng tuyển trả về cho FE."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    candidate_profile_id: int
    job_id: int
    status: ApplicationStatus
    employer_notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationCandidateOut(BaseModel):
    """Đơn ứng tuyển nhìn từ phía ứng viên.

    Cố ý **không** có `employer_notes` (ghi chú nội bộ của nhà tuyển dụng)
    để không lộ thông tin nội bộ cho ứng viên.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_profile_id: int
    job_id: int
    job_title: str
    company_name: str
    status: ApplicationStatus
    cv_id: int | None = None
    cover_letter: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationPageOut(BaseModel):
    """Kết quả danh sách đơn ứng tuyển có phân trang."""
    items: list[ApplicationCandidateOut]
    total: int
    page: int
    page_size: int
    total_pages: int
