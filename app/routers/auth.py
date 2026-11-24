"""API xác thực: đăng ký, đăng nhập, quên và đặt lại mật khẩu."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import auth_rate_limiter
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.crud import company as company_crud
from app.crud import user as user_crud
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordOut,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordOut,
    ResetPasswordRequest,
    TokenOut,
    UserOut,
)
from app.services.password_reset import request_password_reset, reset_password_with_code

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản mới",
)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Đăng ký tài khoản với role **candidate** hoặc **employer**.

    - Employer phải gửi thêm `company_name` — công ty sẽ được tạo ở trạng thái **nháp**.
    - Email đã tồn tại → **409 Conflict**.
    """
    # Kiểm tra email trùng → 409
    if user_crud.get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{data.email}' đã được sử dụng",
        )

    # Tạo user
    user = user_crud.create_user(
        db,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=data.role,
    )

    # Nếu là employer → tạo công ty nháp
    if data.role == "employer":
        company_crud.create_draft_company(db, name=data.company_name, employer_id=user.id)  # type: ignore[arg-type]

    return user


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Đăng nhập, nhận JWT",
)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Đăng nhập bằng email + mật khẩu, nhận `access_token` (JWT).

    Sau đó gắn token vào header mọi request cần xác thực:
    `Authorization: Bearer <access_token>`
    """
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = auth_rate_limiter.check_login_allowed(client_ip, data.email)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều lần đăng nhập không thành công. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)},
        )

    user = user_crud.get_user_by_email(db, data.email)

    # Không tìm thấy hoặc sai mật khẩu → cùng báo lỗi chung (tránh lộ thông tin)
    if not user or not verify_password(data.password, user.password):
        auth_rate_limiter.record_login_failure(client_ip, data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.",
        )

    auth_rate_limiter.record_login_success(client_ip, data.email)
    token = create_access_token(user.id, user.role, getattr(user, "token_version", 1))
    return {"access_token": token, "token_type": "bearer"}


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordOut,
    summary="Yêu cầu mã đặt lại mật khẩu",
)
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Gửi mã xác nhận 6 số đặt lại mật khẩu qua email."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return request_password_reset(db, data.email, ip_address=ip, user_agent=ua)


@router.post(
    "/reset-password",
    response_model=ResetPasswordOut,
    summary="Đặt lại mật khẩu với mã xác nhận",
)
def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Xác thực mã 6 số và cập nhật mật khẩu mới, hủy toàn bộ phiên cũ."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = auth_rate_limiter.check_reset_password_allowed(client_ip, max_requests=10)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều yêu cầu thử mã đặt lại mật khẩu. Vui lòng đợi {retry_after} giây.",
            headers={"Retry-After": str(retry_after)},
        )
    return reset_password_with_code(db, data.email, data.code, data.new_password)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Lấy thông tin user đang đăng nhập",
)
def me(current_user=Depends(get_current_user)):
    """Trả về thông tin user đang đăng nhập dựa trên JWT.

    Cần header: `Authorization: Bearer <access_token>`
    """
    return current_user


@router.post(
    "/logout",
    summary="Đăng xuất tài khoản và thu hồi JWT hiện tại",
)
def logout(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tăng token_version để vô hiệu hoá mọi JWT đã cấp trước đó của người dùng."""
    current_user.token_version = (getattr(current_user, "token_version", 1) or 1) + 1
    db.commit()
    return {"message": "Đã đăng xuất thành công"}

