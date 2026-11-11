from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint("candidate_profile_id", "job_id", name="uq_saved_profile_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_profile_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jobs.id"), nullable=False
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )