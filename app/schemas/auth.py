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


class ForgotPasswordRequest(BaseModel):
    """Yêu cầu gửi mã đặt lại mật khẩu."""

    email: str = Field(min_length=3, max_length=255, examples=["user@example.com"])

    @model_validator(mode="after")
    def clean_email(self) -> "ForgotPasswordRequest":
        self.email = self.email.strip().lower()
        if "@" not in self.email or "." not in self.email:
            raise ValueError("Email không đúng định dạng")
        return self


class ForgotPasswordOut(BaseModel):
    message: str
    cooldown_seconds: int = 60


class ResetPasswordRequest(BaseModel):
    """Dữ liệu xác nhận mã và đặt lại mật khẩu mới."""

    email: str = Field(min_length=3, max_length=255, examples=["user@example.com"])
    code: str = Field(min_length=4, max_length=10, examples=["123456"])
    new_password: str = Field(min_length=6, max_length=128, examples=["newpassword123"])

    @model_validator(mode="after")
    def clean_fields(self) -> "ResetPasswordRequest":
        self.email = self.email.strip().lower()
        self.code = self.code.strip()
        if len(self.new_password) < 6:
            raise ValueError("Mật khẩu mới phải có ít nhất 6 ký tự")
        return self


class ResetPasswordOut(BaseModel):
    message: str
