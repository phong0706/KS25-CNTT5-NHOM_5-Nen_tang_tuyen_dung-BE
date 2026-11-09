"""Tiện ích bảo mật: hash mật khẩu, tạo/xác thực JWT, dependency get_current_user."""
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

ALGORITHM = "HS256"

# HTTPBearer: FastAPI tự đọc header "Authorization: Bearer <token>"
# auto_error=False để trả 401 tuỳ chỉnh thay vì 403 mặc định
_bearer = HTTPBearer(auto_error=False)


# ---------- Password ----------

def hash_password(plain: str) -> str:
    """Hash mật khẩu bằng bcrypt trước khi lưu vào DB."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu người dùng nhập có khớp với hash trong DB không."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------- JWT ----------

def create_access_token(user_id: int, role: str) -> str:
    """Tạo JWT chứa user_id và role, hết hạn sau JWT_EXPIRE_MINUTES phút."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


# ---------- Dependency ----------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """FastAPI dependency: giải mã JWT, trả về User đang đăng nhập.

    Dùng trong router:
        current_user = Depends(get_current_user)
    """
    # Import lazy tránh circular (security ← crud ← models ← db)
    from app.crud.user import get_user_by_id  # noqa: PLC0415

    _unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise _unauth

    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise _unauth

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại")
    return user
