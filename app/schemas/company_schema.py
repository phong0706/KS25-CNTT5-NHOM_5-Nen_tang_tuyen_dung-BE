"""Schema = hình dạng dữ liệu đi vào (request) và đi ra (response) của API Company.

FastAPI dùng schema để tự kiểm tra dữ liệu: sai kiểu / thiếu trường -> trả lỗi 422.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.company import CompanyStatus


class CompanyBase(BaseModel):
    owner_id: int = Field(examples=[2], description="ID user (employer) làm chủ công ty")
    name: str = Field(min_length=1, max_length=255, examples=["FPT Software"])
    logo: str | None = Field(default=None, max_length=500, examples=["https://example.com/logos/fpt.png"])
    cover_image: str | None = Field(default=None, max_length=500, examples=["https://example.com/covers/fpt.png"])
    tax_code: str | None = Field(default=None, max_length=50, examples=["0301363748"])
    company_size: str | None = Field(default=None, max_length=50, examples=["1000+"])
    industry_id: int | None = Field(default=None, examples=[1])
    address: str | None = Field(default=None, max_length=500, examples=["17 Tố Hữu, Hà Nội"])
    website: str | None = Field(default=None, max_length=255, examples=["https://fpt.com"])
    description: str | None = Field(default=None, examples=["Công ty hàng đầu về CNTT"])
    status: CompanyStatus = Field(default=CompanyStatus.PENDING, examples=[CompanyStatus.PENDING])


class CompanyCreate(CompanyBase):
    """Dữ liệu FE gửi lên khi THÊM MỚI công ty (mặc định trạng thái PENDING)."""


class CompanyUpdate(BaseModel):
    """Dữ liệu FE gửi lên khi SỬA. Trường nào không gửi thì giữ nguyên."""

    owner_id: int | None = Field(default=None, examples=[2])
    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo: str | None = Field(default=None, max_length=500)
    cover_image: str | None = Field(default=None, max_length=500)
    tax_code: str | None = Field(default=None, max_length=50)
    company_size: str | None = Field(default=None, max_length=50)
    industry_id: int | None = Field(default=None, examples=[1])
    address: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: CompanyStatus | None = Field(default=None, examples=[CompanyStatus.VERIFIED])


class CompanyProfileUpdate(BaseModel):
    """Dữ liệu employer tự sửa hồ sơ công ty của mình.

    KHÔNG cho employer tự đổi `status` (chỉ admin mới đổi) và `owner_id`.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255, examples=["FPT Software"])
    tax_code: str | None = Field(default=None, max_length=50, examples=["0301363748"])
    company_size: str | None = Field(default=None, max_length=50, examples=["1000+"])
    industry_id: int | None = Field(default=None, examples=[1])
    address: str | None = Field(default=None, max_length=500, examples=["17 Tố Hữu, Hà Nội"])
    website: str | None = Field(default=None, max_length=255, examples=["https://fpt.com"])
    description: str | None = Field(default=None, examples=["Công ty hàng đầu về CNTT"])


class CompanyResponse(CompanyBase):
    """Dữ liệu API trả về cho FE (có kèm theo ID và thời gian)."""

    id: int
    employer_id: int
    is_draft: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
