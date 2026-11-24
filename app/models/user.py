"""Model cho bảng users (đã tạo bằng sql/init.sql, SQLAlchemy chỉ map lại)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, event, func, inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import is_bcrypt_hash
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Dùng String(20) thay vì Enum để không xung đột với ENUM đã có sẵn trong DB
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lý do bị admin khoá (NULL = chưa từng khoá / đã mở khoá)
    locked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


@event.listens_for(User, "before_insert")
def _enforce_bcrypt_password_on_insert(mapper, connection, target: User) -> None:
    """Chốt chặn ORM khi tạo mới: không cho phép lưu mật khẩu thô hoặc hash không phải bcrypt."""
    if not is_bcrypt_hash(target.password):
        raise ValueError("Mật khẩu User phải được băm bằng bcrypt trước khi lưu vào DB")


@event.listens_for(User, "before_update")
def _enforce_bcrypt_password_on_update(mapper, connection, target: User) -> None:
    """Chốt chặn ORM khi cập nhật password: không cho phép ghi đè bằng mật khẩu thô."""
    hist = inspect(target).attrs.password.history
    if hist.has_changes() and not is_bcrypt_hash(target.password):
        raise ValueError("Mật khẩu User phải được băm bằng bcrypt trước khi lưu vào DB")
