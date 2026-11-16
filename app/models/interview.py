"""Model Interview - Lịch phỏng vấn cho đơn ứng tuyển."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Interview(Base):
    """Lịch phỏng vấn cho đơn ứng tuyển.
    
    Một đơn ứng tuyển có thể có nhiều lịch phỏng vấn (vòng 1, vòng 2, ...).
    """
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Đơn ứng tuyển liên quan
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Thời gian phỏng vấn
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Hình thức phỏng vấn: ONLINE (video call) hoặc OFFLINE (trực tiếp)
    interview_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Địa điểm (nếu OFFLINE) hoặc link (nếu ONLINE)
    location_or_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Trạng thái lịch phỏng vấn: SCHEDULED / COMPLETED / CANCELLED
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SCHEDULED", index=True)
    
    # Ghi chú về cuộc phỏng vấn
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
