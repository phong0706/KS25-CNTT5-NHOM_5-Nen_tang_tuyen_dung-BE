"""Models cho báo cáo vi phạm"""

from enum import Enum
from sqlalchemy import Integer, Text, ForeignKey, Enum as SQLEnum
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
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    post_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(SQLEnum(ReportStatus), default=ReportStatus.PENDING, nullable=False)
    resolution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
