"""Model Company (thông tin công ty / nhà tuyển dụng).

Trạng thái vòng đời:
PENDING  -> công ty mới tạo, chờ admin xác minh
VERIFIED -> đã được xác minh (hồ sơ hợp lệ)
REJECTED -> bị từ chối (thông tin không hợp lệ)
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CompanyStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Khóa ngoại liên kết tới bảng users (tự xóa khi user bị xóa)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ID người sở hữu (hỗ trợ truy vấn nhanh theo owner)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Tên công ty
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # URL logo (jpg/png, do server lưu hoặc URL ngoài)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # URL ảnh bìa
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Mã số thuế
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Quy mô công ty, vd: "1-50", "51-200", "1000+"
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Liên kết ngành nghề (FK mềm – không ràng buộc CASCADE để không block khi xóa industry)
    industry_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Địa chỉ
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Website
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Mô tả công ty
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Trạng thái xác minh của Admin
    status: Mapped[CompanyStatus] = mapped_column(
        SQLEnum(CompanyStatus), default=CompanyStatus.PENDING, nullable=False
    )

    # Cờ đánh dấu công ty nháp lúc đăng ký
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)

    # Thời gian tạo / cập nhật
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )