"""Model Notification - Thông báo cho người dùng."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Notification(Base):
    """Thông báo gửi đến người dùng.
    
    Dùng để thông báo các sự kiện như:
    - Nhà tuyển dụng nhận được đơn ứng tuyển mới
    - Ứng viên được mời phỏng vấn
    - Trạng thái đơn ứng tuyển thay đổi
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Người nhận thông báo
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Loại thông báo (để FE hiển thị icon/màu sắc khác nhau)
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # VD: "NEW_APPLICATION", "INTERVIEW_INVITE", "STATUS_CHANGE"
    
    # Tiêu đề thông báo
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Nội dung chi tiết
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Link liên quan (VD: /applications/123, /jobs/456)
    related_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Đã đọc chưa
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    
    # Thời gian tạo và đọc
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
