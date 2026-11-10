"""Schema cho Interview - Lịch phỏng vấn."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------
class InterviewBase(BaseModel):
    """Base schema cho Interview."""
    scheduled_at: datetime = Field(examples=["2026-12-15T14:00:00"])
    interview_type: str = Field(min_length=1, max_length=50, examples=["ONLINE"])
    location_or_link: str | None = Field(default=None, max_length=500, examples=["https://meet.google.com/abc-defg-hij"])
    status: str = Field(default="SCHEDULED", max_length=50, examples=["SCHEDULED"])
    notes: str | None = Field(default=None, examples=["Phỏng vấn vòng 1 với HR"])


class InterviewCreate(InterviewBase):
    """Dữ liệu FE gửi lên khi tạo lịch phỏng vấn mới."""
    application_id: int = Field(examples=[1])


class InterviewUpdate(BaseModel):
    """Dữ liệu FE gửi lên khi cập nhật lịch phỏng vấn."""
    scheduled_at: datetime | None = None
    interview_type: str | None = Field(default=None, min_length=1, max_length=50)
    location_or_link: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class InterviewOut(InterviewBase):
    """Dữ liệu lịch phỏng vấn trả về cho FE."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime
