"""Model cho hệ thống tính điểm phù hợp việc làm (Matching Engine).
Giới hạn: <= 200 dòng.
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MatchScore(Base):
    __tablename__ = "match_scores"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uk_match_cand_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    total_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    skill_score: Mapped[float] = mapped_column(Float, nullable=False)
    level_score: Mapped[float] = mapped_column(Float, nullable=False)
    place_score: Mapped[float] = mapped_column(Float, nullable=False)
    salary_score: Mapped[float] = mapped_column(Float, nullable=False)

    matched_skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_required_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0")

    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    is_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class CandidateMatchingSetting(Base):
    __tablename__ = "candidate_matching_settings"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    open_to_relocate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SkillJobIndex(Base):
    __tablename__ = "skill_job_index"
    __table_args__ = (
        UniqueConstraint("skill_canonical", "job_id", name="uk_skill_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    skill_canonical: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
