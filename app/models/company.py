"""Model Company (thông tin công ty / nhà tuyển dụng).

Trạng thái vòng đời:
PENDING  -> công ty mới tạo, chờ admin xác minh
VERIFIED -> đã được xác minh (hồ sơ hợp lệ)
REJECTED -> bị từ chối (thông tin không hợp lệ)
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CompanyStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # chủ tài khoản (user có role = employer). Lưu dạng Integer giống report.py
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)