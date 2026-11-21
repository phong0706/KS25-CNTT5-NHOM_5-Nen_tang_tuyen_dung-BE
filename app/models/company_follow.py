"""Model theo dõi công ty của ứng viên."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CompanyFollow(Base):
    __tablename__ = "company_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_company_follows_user_company"),
        Index("idx_company_follows_company", "company_id"),
        Index("idx_company_follows_user_followed", "user_id", "followed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    followed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
