"""Tiện ích bảo mật: hash mật khẩu, tạo/xác thực JWT, dependency xác thực."""
from datetime import datetime, timedelta, timezone
from typing import Callable

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    """Hash mật khẩu bằng bcrypt trước khi lưu vào DB."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu người dùng nhập có khớp với mật khẩu trong DB.

    Chỉ chấp nhận bcrypt hash hợp lệ ($2a$/$2b$/$2y$).
    Từ chối mọi giá trị không phải bcrypt — bao gồm plaintext — để ngăn
    tấn công bypassing khi DB chứa giá trị không phải hash (SEC-CRIT-01).
    """
    if not hashed:
        return False
    if not hashed.startswith(("$2a$", "$2b$", "$2y$")):
        # Không phải bcrypt hash → từ chối ngay, không so sánh plaintext
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int, role: str, token_version: int = 1) -> str:
    """Tạo JWT chứa user_id, role và token_ver, hết hạn sau JWT_EXPIRE_MINUTES."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "token_ver": token_version, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def _extract_payload(credentials: HTTPAuthorizationCredentials) -> dict | None:
    try:
        return jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except (JWTError, KeyError, ValueError):
        return None


def _extract_user_id(credentials: HTTPAuthorizationCredentials) -> int | None:
    payload = _extract_payload(credentials)
    if not payload or "sub" not in payload:
        return None
    try:
        return int(payload["sub"])
    except (ValueError, TypeError):
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    from app.crud.user import get_user_by_id  # noqa: PLC0415

    _unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise _unauth

    payload = _extract_payload(credentials)
    if not payload or "sub" not in payload:
        raise _unauth

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise _unauth

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_ver = payload.get("token_ver")
    if token_ver is not None and getattr(user, "token_version", 1) != token_ver:
        raise _unauth

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.",
        )

    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    from app.crud.user import get_user_by_id  # noqa: PLC0415

    if credentials is None:
        return None

    payload = _extract_payload(credentials)
    if not payload or "sub" not in payload:
        return None

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        return None

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        return None

    token_ver = payload.get("token_ver")
    if token_ver is not None and getattr(user, "token_version", 1) != token_ver:
        return None

    return user


def role_required(*roles: str) -> Callable:
    """Factory tạo dependency kiểm tra role."""
    def _check(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Chức năng này chỉ dành cho: {', '.join(roles)}",
            )
        return current_user

    return _check
