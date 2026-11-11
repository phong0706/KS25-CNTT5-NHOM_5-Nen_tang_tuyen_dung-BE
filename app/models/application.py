"""Model Application - Đơn ứng tuyển của ứng viên vào tin tuyển dụng."""
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
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


class Application(Base):
    """Đơn ứng tuyển - liên kết ứng viên với tin tuyển dụng.
    
    Một ứng viên chỉ được nộp 1 đơn cho 1 tin tuyển dụng (UNIQUE constraint).
    """
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_profile_id", "job_id", name="uq_application_candidate_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Ứng viên nộp đơn
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Tin tuyển dụng được ứng tuyển
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # CV đính kèm (có thể null nếu ứng viên chưa upload CV)
    cv_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cvs.id", ondelete="SET NULL"), nullable=True
    )
    
    # Thư giới thiệu
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Trạng thái đơn ứng tuyển
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(ApplicationStatus), default=ApplicationStatus.SUBMITTED, nullable=False, index=True
    )
    
    # Ghi chú của nhà tuyển dụng
    employer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
