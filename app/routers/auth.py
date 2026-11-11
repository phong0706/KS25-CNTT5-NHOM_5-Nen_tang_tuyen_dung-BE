"""API xác thực.

    POST /api/auth/register  đăng ký (candidate hoặc employer)
    POST /api/auth/login     đăng nhập, nhận JWT
    GET  /api/auth/me        thông tin user đang đăng nhập (cần Bearer token)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.crud import company as company_crud
from app.crud import user as user_crud
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut

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
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Đăng nhập bằng email + mật khẩu, nhận `access_token` (JWT).

    Sau đó gắn token vào header mọi request cần xác thực:
    `Authorization: Bearer <access_token>`
    """
    user = user_crud.get_user_by_email(db, data.email)

    # Không tìm thấy hoặc sai mật khẩu → cùng báo lỗi chung (tránh lộ thông tin)
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.",
        )

    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer"}


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
