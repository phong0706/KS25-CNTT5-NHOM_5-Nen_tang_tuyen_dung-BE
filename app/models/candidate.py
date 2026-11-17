"""Models cho ứng viên: hồ sơ, kỹ năng, kinh nghiệm, học vấn và CV."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CandidateProfile(Base):
    """Hồ sơ ứng viên — quan hệ 1-1 với bảng users (liên kết qua user_id)."""

    __tablename__ = "candidate_profiles"
    # Trùng ten bang voi app.models.candidate_profile.CandidateProfile (nhanh cu):
    # extend_existing=True de SQLAlchemy gop cot thay vi nem InvalidRequestError.
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )

    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)