"""Schema cho API quản lý tài khoản người dùng (admin)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["candidate", "employer", "admin"]


class UserOut(BaseModel):
    """Thông tin tài khoản trả về cho client (không có password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    role: str
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    locked_reason: str | None
    created_at: datetime
    updated_at: datetime


class UserListOut(BaseModel):
    """Kết quả danh sách tài khoản có phân trang."""

    items: list[UserOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserLockIn(BaseModel):
    """Lý do khoá tài khoản (bắt buộc, tối đa 500 ký tự)."""

    locked_reason: str = Field(
        min_length=1, max_length=500, examples=["Vi phạm nội quy diễn đàn"]
    )


__all__ = ["UserOut", "UserListOut", "UserLockIn", "UserRole"]