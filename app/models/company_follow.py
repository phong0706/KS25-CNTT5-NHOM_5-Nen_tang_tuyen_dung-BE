"""Model cho quan hệ theo dõi giữa ứng viên và công ty."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CompanyFollow(Base):
    __tablename__ = "company_follows"
    __table_args__ = (
        UniqueConstraint("candidate_id", "company_id", name="uq_company_follows_candidate_company"),
        Index("idx_company_follows_company", "company_id"),
        Index("idx_company_follows_candidate_created", "candidate_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
