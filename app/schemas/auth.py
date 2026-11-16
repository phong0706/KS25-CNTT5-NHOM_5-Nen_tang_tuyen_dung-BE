"""Schema cho các API xác thực: đăng ký, đăng nhập, thông tin cá nhân."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterRequest(BaseModel):
    """Dữ liệu đăng ký tài khoản mới."""

    email: str = Field(examples=["user@example.com"])
    password: str = Field(min_length=6, examples=["secret123"])
    full_name: str = Field(min_length=1, max_length=255, examples=["Nguyễn Văn A"])
    phone: str | None = Field(default=None, examples=["0912345678"])
    role: Literal["candidate", "employer"] = Field(
        default="candidate",
        examples=["candidate"],
        description="Chọn 'candidate' (ứng viên) hoặc 'employer' (nhà tuyển dụng)",
    )
    company_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        examples=["Công ty TNHH ABC"],
        description="Bắt buộc khi role=employer. Công ty sẽ được tạo ở trạng thái nháp.",
    )

    @model_validator(mode="after")
    def employer_must_have_company(self) -> "RegisterRequest":
        if self.role == "employer" and not self.company_name:
            raise ValueError("Nhà tuyển dụng (employer) phải nhập tên công ty (company_name)")
        return self


class LoginRequest(BaseModel):
    """Thông tin đăng nhập."""

    email: str = Field(examples=["admin@tuyendung.com"])
    password: str = Field(examples=["admin123@"])


class TokenOut(BaseModel):
    """JWT trả về sau khi đăng nhập thành công."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Thông tin user trả về cho client (không có password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    role: str
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
