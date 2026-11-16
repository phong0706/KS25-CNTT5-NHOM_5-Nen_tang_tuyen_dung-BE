"""Model cho bảng notifications (thông báo trong ứng dụng).

Bảng này được tạo tự động bởi Base.metadata.create_all() khi khởi động server
(xem app/main.py). Script SQL tương ứng cho nhóm: sql/patch_notifications.sql.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class Notification(Base):
    """Một thông báo gửi tới 1 người dùng.

    - user_id : người nhận (bắt buộc) — luôn là người đang đăng nhập ở phía FE
    - actor_id: người gây ra sự kiện (có thể NULL, ví dụ hệ thống tự sinh)
    - type    : mã loại thông báo, xem app/services/notification.py
    - link    : đường dẫn FE sẽ mở khi bấm vào thông báo
    - ref_type / ref_id: con trỏ tới đối tượng liên quan (application, job, ...)
    - dedupe_key: khoá chống tạo trùng (duy nhất theo user)
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user_created", "user_id", "created_at"),
        Index("idx_notifications_user_unread", "user_id", "is_read"),
        UniqueConstraint(
            "user_id", "dedupe_key", name="uq_notifications_user_dedupe"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Khoá chống trùng: ví dụ "application:{id}:submitted" — NULL = không chống trùng
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
