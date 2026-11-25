"""Models cho hồ sơ ứng tuyển: CV, Application, lịch sử trạng thái, nháp thư, mẫu thư."""
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ApplicationStatus(str, Enum):
    """Trạng thái đơn ứng tuyển."""

    SUBMITTED = "SUBMITTED"      # Đã nộp
    REVIEWING = "REVIEWING"      # Đang xem xét
    INTERVIEW = "INTERVIEW"      # Mời phỏng vấn
    OFFERED = "OFFERED"          # Đã nhận offer
    REJECTED = "REJECTED"        # Bị từ chối
    WITHDRAWN = "WITHDRAWN"      # Ứng viên rút đơn


class CV(Base):
    __tablename__ = "cvs"
    __table_args__ = (
        Index("idx_cvs_candidate_id", "candidate_id"),
        Index("idx_cvs_candidate_deleted", "candidate_id", "deleted_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    @property
    def file_size(self) -> int:
        return self.size_bytes or 0

    @file_size.setter
    def file_size(self, val: int) -> None:
        self.size_bytes = val

    @property
    def uploaded_at(self) -> datetime:
        return self.created_at

    @property
    def profile_id(self) -> int | None:
        return self.candidate_id

    @profile_id.setter
    def profile_id(self, val: int | None) -> None:
        self.candidate_id = val


class Application(Base):
    """Đơn ứng tuyển - liên kết ứng viên với tin tuyển dụng."""

    __tablename__ = "applications"
    __table_args__ = (
        Index("idx_apps_candidate_id", "candidate_id"),
        Index("idx_apps_status", "status"),
        Index("idx_apps_created_at", "created_at"),
        UniqueConstraint(
            "candidate_profile_id", "job_id", name="uq_application_candidate_job"
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Ứng viên nộp đơn (hỗ trợ cả user_id từ feat và candidate_profile_id từ develop)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    candidate_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Tin tuyển dụng được ứng tuyển
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # CV đính kèm
    cv_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cvs.id", ondelete="SET NULL"), nullable=True
    )
    cv_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Thư giới thiệu & ghi chú
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    employer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Trạng thái đơn ứng tuyển
    status: Mapped[str] = mapped_column(
        String(32),
        default=ApplicationStatus.SUBMITTED.value,
        nullable=False,
    )
    active_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    withdraw_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_mode: Mapped[str | None] = mapped_column(String(80), nullable=True)
    interview_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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


class ApplicationNote(Base):
    __tablename__ = "application_notes"
    __table_args__ = (Index("idx_app_notes_app_id", "application_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        Index("idx_interviews_app_id", "application_id"),
        Index("idx_interviews_scheduled_at", "scheduled_at"),
        Index("idx_interviews_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=45)
    mode: Mapped[str] = mapped_column(String(80), default="Trực tuyến qua Google Meet")
    interview_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_or_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    interviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MetaRejectionReason(Base):
    __tablename__ = "meta_rejection_reasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)