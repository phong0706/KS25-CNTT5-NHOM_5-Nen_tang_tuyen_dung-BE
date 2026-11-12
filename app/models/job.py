"""Model Job - Tin tuyển dụng của doanh nghiệp."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Job(Base):
    """Bảng tin tuyển dụng với đầy đủ các index phục vụ tìm kiếm, lọc và sắp xếp."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_status_deadline", "status", "deadline"),
        Index("idx_jobs_company", "company_id"),
        Index("idx_jobs_industry", "industry_id"),
        Index("idx_jobs_location", "location_id"),
        Index("idx_jobs_job_type", "job_type"),
        Index("idx_jobs_experience_level", "experience_level"),
        Index("idx_jobs_salary", "salary_min", "salary_max"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_title", "title"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    posted_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    industry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("industries.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("locations.id"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(20), nullable=False, default="FULLTIME")
    experience_level: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    salary_min: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    is_negotiable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="VND")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    views_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
