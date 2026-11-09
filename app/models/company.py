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
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # quy mô nhân sự, vd: "1-50", "51-200", "201-500", "501-1000", "1000+"
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ngành nghề (link tới industries). Lưu dạng Integer giống report.py
    industry_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[CompanyStatus] = mapped_column(
        SQLEnum(CompanyStatus), default=CompanyStatus.PENDING, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
