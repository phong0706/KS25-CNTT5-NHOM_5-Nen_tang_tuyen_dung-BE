"""Model nhật ký lượt xem hồ sơ ứng viên của nhà tuyển dụng."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProfileView(Base):
    """Bảng ghi nhận lượt xem hồ sơ ứng viên (SEC: rate limit, debounce 30 phút)."""

    __tablename__ = "profile_views"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employer_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    context: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_pv_candidate_viewed", "candidate_user_id", "viewed_at"),
    )
