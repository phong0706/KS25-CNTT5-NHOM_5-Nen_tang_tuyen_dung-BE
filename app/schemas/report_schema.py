"""Schemas cho báo cáo vi phạm"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.report import ReportStatus


class ReportCreate(BaseModel):
    """Dữ liệu FE gửi lên khi tạo báo cáo vi phạm mới."""

    post_id: int = Field(examples=[1])
    reason: str = Field(
        min_length=5,
        max_length=2000,
        examples=["Nội dung tin đăng lừa đảo, sai sự thật"],
    )

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Lý do báo cáo phải có ít nhất 5 ký tự.")
        return value


class ReportActionIn(BaseModel):
    """Quyết định kiểm duyệt và kết quả cần lưu vào báo cáo."""

    status: Literal["RESOLVED", "REJECTED"]
    resolution_result: str = Field(min_length=5, max_length=2000)

    @field_validator("resolution_result")
    @classmethod
    def strip_resolution_result(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Kết quả xử lý phải có ít nhất 5 ký tự.")
        return value


class ReportUpdate(BaseModel):
    """Schema genérico preservado para compatibilidade com clientes existentes."""

    status: ReportStatus
    resolution_result: str | None = None


class ReportResponse(BaseModel):
    """Dữ liệu báo cáo vi phạm trả về cho FE."""

    id: int
    reporter_id: int
    post_id: int
    employer_id: int
    reason: str
    status: ReportStatus
    resolution_result: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminReportListOut(BaseModel):
    """Danh sách báo cáo cho admin."""
    id: int
    post_id: int
    reporter_full_name: str | None = None
    reporter_email: str | None = None
    post_title: str | None = None
    employer_full_name: str | None = None
    reason: str
    status: ReportStatus
    resolution_result: str | None = None
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminReportPageOut(BaseModel):
    """Một trang báo cáo kèm tổng số kết quả sau lọc."""

    items: list[AdminReportListOut]
    total: int
    skip: int
    limit: int


class AdminReportActionOut(BaseModel):
    """Kết quả hành động admin trên báo cáo."""
    id: int
    action: str  # "resolved" hoặc "rejected"
    message: str
    job_hidden: bool = False