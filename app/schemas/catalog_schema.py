"""Schemas cho các danh mục: Industry, Location, Skill"""
from pydantic import BaseModel, ConfigDict, Field

class CatalogBase(BaseModel):
    """Base schema cho danh mục"""
    name: str = Field(min_length=1, max_length=255, examples=["Công nghệ thông tin"])
    status: str = Field(default="active", examples=["active"])

class CatalogCreate(CatalogBase):
    """Dữ liệu FE gửi lên khi THÊM MỚI ngành, địa điểm hoặc kỹ năng."""
    pass

class CatalogUpdate(BaseModel):
    """Dữ liệu FE gửi lên khi SỬA. Trường nào không gửi thì giữ nguyên."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None)

class CatalogResponse(CatalogBase):
    """Dữ liệu trả về cho FE (có kèm theo ID)."""
    id: int

    model_config = ConfigDict(from_attributes=True)
