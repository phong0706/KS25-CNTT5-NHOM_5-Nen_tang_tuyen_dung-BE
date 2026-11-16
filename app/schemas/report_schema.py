"""Schemas cho báo cáo vi phạm"""

from pydantic import BaseModel, ConfigDict, Field
from app.models.report import ReportStatus


class ReportCreate(BaseModel):
    """Dữ liệu FE gửi lên khi tạo báo cáo vi phạm mới."""

    post_id: int = Field(examples=[1])
    reason: str = Field(min_length=5, examples=["Nội dung tin đăng lừa đảo, sai sự thật"])


class ReportUpdate(BaseModel):
    """Dữ liệu Admin dùng để cập nhật trạng thái xử lý báo cáo."""

    status: ReportStatus = Field(examples=[ReportStatus.RESOLVED])
    resolution_result: str | None = Field(default=None, examples=["Đã xóa bài viết và cảnh cáo tài khoản vi phạm"])


class ReportResponse(BaseModel):
    """Dữ liệu báo cáo vi phạm trả về cho FE."""

    id: int
    user_id: int
    post_id: int
    reason: str
    status: ReportStatus
    resolution_result: str | None = None

    model_config = ConfigDict(from_attributes=True)
