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

    # Khóa ngoại liên kết tới bảng users (từ nhánh feat - tự xóa khi user bị xóa)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ID người sở hữu (từ nhánh develop - hỗ trợ truy vấn nhanh theo owner)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Tên công ty
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Trạng thái xác minh của Admin (từ nhánh develop)
    status: Mapped[CompanyStatus] = mapped_column(
        SQLEnum(CompanyStatus), default=CompanyStatus.PENDING, nullable=False
    )

    # Cờ đánh dấu công ty nháp lúc đăng ký (từ nhánh feat)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)