"""Models cho hồ sơ ứng tuyển: CV, Application, lịch sử trạng thái, nháp thư, mẫu thư."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CV(Base):
    __tablename__ = "cvs"
    __table_args__ = (Index("idx_cvs_candidate_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("idx_apps_candidate_id", "candidate_id"),
        Index("idx_apps_status", "status"),
        Index("idx_apps_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("cvs.id", ondelete="SET NULL"), nullable=True
    )
    cv_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    withdraw_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_mode: Mapped[str | None] = mapped_column(String(80), nullable=True)
    interview_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"
    __table_args__ = (Index("idx_ash_app_id", "application_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MetaApplicationStatus(Base):
    __tablename__ = "meta_application_statuses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    tone: Mapped[str] = mapped_column(String(30), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(default=False)


class MetaWithdrawReason(Base):
    __tablename__ = "meta_withdraw_reasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class CoverLetterTemplate(Base):
    __tablename__ = "cover_letter_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ApplicationDraft(Base):
    __tablename__ = "application_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SavedSearch(Base):
    """Bộ lọc tìm kiếm đã lưu của ứng viên.

    Lưu ý: bảng này trước đây KHÔNG có trong bất kỳ file SQL nào, khiến
    /api/candidate/saved-searches luôn trả lỗi 500 (Table doesn't exist).
    Model này giúp Base.metadata.create_all() tự tạo bảng khi khởi động server.
    """

    __tablename__ = "saved_searches"
    __table_args__ = (
        Index("idx_saved_searches_user_id", "user_id"),
        Index("idx_saved_searches_user_name", "user_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

