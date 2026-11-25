"""Models cho báo cáo vi phạm"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReportStatus(str, Enum):
    """Trạng thái xử lý báo cáo"""

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class Report(Base):
    """Báo cáo vi phạm bài đăng"""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Người báo cáo")
    post_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Tin tuyển dụng bị báo cáo")
    employer_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Người đăng tin (nhà tuyển dụng)")

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(SQLEnum(ReportStatus), default=ReportStatus.PENDING, nullable=False)
    resolution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
