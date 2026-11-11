"""Tiện ích bảo mật: hash mật khẩu, tạo/xác thực JWT, các dependency xác thực & phân quyền.

Exports chính để các router import:
    get_current_user    — bắt buộc đăng nhập; 401/403 nếu không hợp lệ / bị khoá
    get_optional_user   — tuỳ chọn; trả None nếu khách chưa đăng nhập
    role_required(...)  — factory kiểm tra role; 401/403 nếu sai
"""
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

# auto_error=False → FastAPI không tự ném 403; ta tự kiểm soát lỗi 401 bên dưới
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash mật khẩu bằng bcrypt trước khi lưu vào DB."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu người dùng nhập có khớp với hash trong DB không."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, role: str) -> str:
    """Tạo JWT chứa user_id và role, hết hạn sau JWT_EXPIRE_MINUTES phút."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _extract_user_id(credentials: HTTPAuthorizationCredentials) -> int | None:
    """Giải mã JWT → trả user_id (int) hoặc None nếu token sai / hết hạn."""
    try:
        payload = jwt.decode(
            credentials.credentials, settings.JWT_SECRET, algorithms=[ALGORITHM]
        )
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Dependency: get_current_user
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Dependency bắt buộc đăng nhập.

    Luồng kiểm tra:
        1. Thiếu header Authorization       → 401
        2. Token sai định dạng / hết hạn    → 401
        3. user_id trong token không có DB  → 401
        4. Tài khoản bị khoá (is_active=False) → 403

    Cách dùng trong router:
        current_user = Depends(get_current_user)
    """
    from app.crud.user import get_user_by_id  # noqa: PLC0415

    _unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise _unauth

    user_id = _extract_user_id(credentials)
    if user_id is None:
        raise _unauth

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Kiểm tra khoá tài khoản SAU khi xác thực token
    # → tài khoản bị khoá sau khi đăng nhập vẫn bị chặn ngay lần sau
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.",
        )

    return user


# ---------------------------------------------------------------------------
# Dependency: get_optional_user
# ---------------------------------------------------------------------------

def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Dependency tuỳ chọn — khách vẫn được phép truy cập.

    - Không có token (khách)        → trả None, không lỗi
    - Token sai / hết hạn           → trả None, không lỗi
    - Token hợp lệ nhưng bị khoá   → trả None, không lỗi
    - Token hợp lệ, tài khoản OK   → trả User object

    Cách dùng trong router:
        current_user = Depends(get_optional_user)   # có thể là None
        if current_user:
            # hiển thị tính năng riêng cho user đã đăng nhập
    """
    from app.crud.user import get_user_by_id  # noqa: PLC0415

    if credentials is None:
        return None

    user_id = _extract_user_id(credentials)
    if user_id is None:
        return None

    user = get_user_by_id(db, user_id)
    # Trả None cho cả: không tìm thấy user và tài khoản bị khoá
    if user is None or not user.is_active:
        return None

    return user


# ---------------------------------------------------------------------------
# Dependency factory: role_required
# ---------------------------------------------------------------------------

def role_required(*roles: str) -> Callable:
    """Factory tạo dependency kiểm tra role.

    Quy tắc lỗi:
        • Chưa đăng nhập / token không hợp lệ → 401  (do get_current_user)
        • Tài khoản bị khoá                   → 403  (do get_current_user)
        • Role không khớp                     → 403

    Cách dùng:
        # Chỉ admin
        current_user = Depends(role_required("admin"))

        # Employer hoặc admin đều được
        current_user = Depends(role_required("employer", "admin"))

    Ví dụ router đầy đủ:
        @router.post("/jobs")
        def create_job(
            data: JobCreate,
            db: Session = Depends(get_db),
            current_user = Depends(role_required("employer")),
        ):
            ...
    """
    def _check(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Chức năng này chỉ dành cho: {', '.join(roles)}",
            )
        return current_user

    return _check
