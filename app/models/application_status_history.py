"""Model ApplicationStatusHistory - Lịch sử thay đổi trạng thái đơn ứng tuyển."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ApplicationStatusHistory(Base):
    """Lịch sử thay đổi trạng thái đơn ứng tuyển.
    
    Mỗi lần trạng thái thay đổi (ví dụ: SUBMITTED -> REVIEWING), 
    hệ thống sẽ tạo 1 bản ghi mới trong bảng này.
    """
    __tablename__ = "application_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Đơn ứng tuyển liên quan
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Trạng thái cũ (nullable vì lần đầu tạo đơn không có trạng thái cũ)
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Trạng thái mới
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Thời gian thay đổi
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Người thay đổi trạng thái (admin hoặc employer)
    changed_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
