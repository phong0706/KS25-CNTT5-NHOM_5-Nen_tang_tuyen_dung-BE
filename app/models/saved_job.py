"""Model SavedJob - Tin tuyển dụng đã lưu của ứng viên."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SavedJob(Base):
    """Bảng lưu tin tuyển dụng yêu thích của ứng viên.

    Mỗi ứng viên chỉ được lưu 1 lần cho mỗi tin tuyển dụng (UNIQUE constraint).
    """

    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint("candidate_profile_id", "job_id", name="uq_saved_profile_job"),
        Index("idx_saved_jobs_candidate", "candidate_profile_id"),
        Index("idx_saved_jobs_job", "job_id"),
        Index("idx_saved_jobs_saved_at", "saved_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )