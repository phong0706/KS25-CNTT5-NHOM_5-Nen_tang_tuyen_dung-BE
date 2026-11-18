"""API quản lý tài khoản người dùng (dành cho admin).

Hỗ trợ:
- Danh sách tài khoản: lọc theo vai trò / trạng thái, tìm kiếm, phân trang
    GET /api/users?role=&is_active=&keyword=&page=&page_size=
    (Tương thích ngược với tham số q, skip, limit)
- Thống kê tổng quan người dùng:
    GET /api/users/stats
- Khoá/Mở khoá nhanh:
    PATCH /api/users/{user_id}/toggle-status
- Khoá tài khoản kèm lý do (sau khi khoá: không đăng nhập được, token cũ cũng bị chặn):
    POST /api/users/{user_id}/lock      {"locked_reason": "..."}
- Mở khoá tài khoản:
    POST /api/users/{user_id}/unlock

Mọi endpoint đều yêu cầu Bearer token của tài khoản role=admin.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserListOut, UserLockIn, UserOut

router = APIRouter(prefix="/users", tags=["Users"])

VALID_ROLES = {"candidate", "employer", "operator", "admin"}


@router.get(
    "",
    response_model=UserListOut,
    summary="Danh sách tài khoản: lọc role/trạng thái, tìm kiếm, phân trang",
)
def list_users(
    role: str | None = Query(
        default=None,
        description="Lọc theo vai trò: candidate | employer | admin",
    ),
    is_active: bool | None = Query(
        default=None,
        description="Lọc theo trạng thái: true = đang hoạt động, false = bị khoá",
    ),
    keyword: str | None = Query(
        default=None,
        description="Tìm kiếm theo email / họ tên / số điện thoại",
    ),
    q: str | None = Query(
        default=None,
        description="Tìm kiếm theo tên hoặc email (tương thích ngược)",
    ),
    page: int = Query(default=1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Số tài khoản mỗi trang (tối đa 100)"
    ),
    skip: int | None = Query(default=None, ge=0, description="Offset (tương thích ngược)"),
    limit: int | None = Query(default=None, ge=1, le=100, description="Limit (tương thích ngược)"),
    current_user: User = Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    """Trả về danh sách tài khoản thoả mãn bộ lọc kèm phân trang."""
    if role is not None and role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "role không hợp lệ. "
                f"Giá trị cho phép: {', '.join(sorted(VALID_ROLES))}"
            ),
        )

    effective_keyword = keyword if keyword is not None else q
    effective_page_size = limit if limit is not None else page_size
    effective_page = (skip // effective_page_size) + 1 if skip is not None else page

    users, total = user_crud.get_users(
        db,
        role=role,
        is_active=is_active,
        keyword=effective_keyword,
        page=effective_page,
        page_size=effective_page_size,
    )
    total_pages = (total + effective_page_size - 1) // effective_page_size if total > 0 else 0

    return UserListOut(
        items=users,
        total=total,
        page=effective_page,
        page_size=effective_page_size,
        total_pages=total_pages,
    )


@router.get("/stats", summary="Thống kê tổng quan người dùng (chỉ Admin)")
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_candidates = db.scalar(select(func.count(User.id)).where(User.role == "candidate")) or 0
    total_employers = db.scalar(select(func.count(User.id)).where(User.role == "employer")) or 0
    total_admins = db.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0

    return {
        "total_users": total_users,
        "total_candidates": total_candidates,
        "total_employers": total_employers,
        "total_admins": total_admins,
        "active_users": active_users,
    }


@router.patch(
    "/{user_id}/toggle-status",
    response_model=UserOut,
    summary="Khoá/Mở khoá nhanh tài khoản (chỉ Admin)",
)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự khoá tài khoản của chính mình",
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")

    user.is_active = not user.is_active
    if user.is_active and hasattr(user, "locked_reason"):
        user.locked_reason = None

    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/{user_id}/lock",
    response_model=UserOut,
    summary="Khoá tài khoản kèm lý do (bị khoá thì không đăng nhập được)",
)
def lock_user(
    user_id: int,
    data: UserLockIn,
    current_user: User = Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    """Khoá tài khoản: `is_active=False` + lưu `locked_reason`.

    - Không tìm thấy tài khoản → **404**
    - Tài khoản đã bị khoá → **400**
    - Sau khi khoá: đăng nhập → **403**, các API cần token → **403** ngay cả khi token còn hạn.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản",
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể khoá chính tài khoản của mình",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản đã bị khoá trước đó",
        )

    return user_crud.lock_user(db, user=user, locked_reason=data.locked_reason)


@router.post(
    "/{user_id}/unlock",
    response_model=UserOut,
    summary="Mở khoá tài khoản (xoá lý do khoá)",
)
def unlock_user(
    user_id: int,
    current_user: User = Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    """Mở khoá tài khoản: `is_active=True` + xoá `locked_reason`.

    - Không tìm thấy tài khoản → **404**
    - Tài khoản chưa bị khoá → **400**
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản",
        )
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản chưa bị khoá",
        )

    return user_crud.unlock_user(db, user=user)