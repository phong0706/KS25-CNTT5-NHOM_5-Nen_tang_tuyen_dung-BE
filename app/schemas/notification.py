"""Schemas Pydantic cho module thông báo."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    """Một thông báo trả về cho FE."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: str | None = None
    link: str | None = None
    ref_type: str | None = None
    ref_id: int | None = None
    is_read: bool = False
    read_at: datetime | None = None
    actor_id: int | None = None
    actor_name: str | None = None
    created_at: datetime


class NotificationListOut(BaseModel):
    """Danh sách thông báo có phân trang."""

    items: list[NotificationOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0
    unread_count: int = 0


class UnreadCountOut(BaseModel):
    """Kết quả đếm số thông báo chưa đọc."""

    unread_count: int = 0


class MarkReadRequest(BaseModel):
    """Body đánh dấu đã đọc (một hoặc nhiều thông báo)."""

    notification_ids: list[int] = Field(..., min_length=1, max_length=100)


class MarkReadResultOut(BaseModel):
    """Kết quả đánh dấu đã đọc."""

    updated: int = 0
    unread_count: int = 0
    message: str = "Đã đánh dấu đã đọc."
