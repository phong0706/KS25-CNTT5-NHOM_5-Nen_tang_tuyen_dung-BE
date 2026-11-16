"""Models cho danh mục meta, tin tuyển dụng (jobs) và hồ sơ ứng tuyển (job_applications)."""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MetaLocation(Base):
    __tablename__ = "meta_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MetaLevel(Base):
    __tablename__ = "meta_levels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MetaWorkType(Base):
    __tablename__ = "meta_work_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MetaCategory(Base):
    __tablename__ = "meta_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(60), nullable=False, default="code")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MetaSkill(Base):
    __tablename__ = "meta_skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_employer_id", "employer_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_location_id", "location_id"),
        Index("idx_jobs_level_id", "level_id"),
        Index("idx_jobs_category_id", "category_id"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_employer_status_created", "employer_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta_locations.id", ondelete="SET NULL"), nullable=True
    )
    level_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta_levels.id", ondelete="SET NULL"), nullable=True
    )
    work_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta_work_types.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta_categories.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    salary_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_salary_negotiable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    benefits: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    views_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        Index("idx_job_app_job_viewed", "job_id", "is_viewed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_viewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (
        Index("idx_saved_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

