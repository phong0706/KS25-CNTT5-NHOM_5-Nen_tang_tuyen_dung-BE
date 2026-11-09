from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_status_deadline", "status", "deadline"),
        Index("idx_jobs_industry", "industry_id"),
        Index("idx_jobs_location", "location_id"),
        Index("idx_jobs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industries.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())