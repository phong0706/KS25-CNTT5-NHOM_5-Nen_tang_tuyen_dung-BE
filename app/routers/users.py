"""API quản lý tài khoản người dùng (dành cho admin).

Hỗ trợ:
- Danh sách tài khoản: lọc theo vai trò / trạng thái, tìm kiếm, phân trang
    GET /api/users?role=&is_active=&keyword=&page=&page_size=
- Khoá tài khoản kèm lý do (sau khi khoá: không đăng nhập được, token cũ cũng bị chặn):
    POST /api/users/{user_id}/lock      {"locked_reason": "..."}
- Mở khoá tài khoản:
    POST /api/users/{user_id}/unlock

Mọi endpoint đều yêu cầu Bearer token của tài khoản role=admin.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserListOut, UserLockIn, UserOut

router = APIRouter(prefix="/users", tags=["Users"])

VALID_ROLES = {"candidate", "employer", "admin"}


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
    page: int = Query(default=1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Số tài khoản mỗi trang (tối đa 100)"
    ),
    current_user: User = Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    """Trả về danh sách tài khoản thoả mãn bộ lọc kèm phân trang.

    - `role` sai giá trị → **400**
    - `page` < 1 hoặc `page_size` > 100 → **422**
    """
    if role is not None and role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "role không hợp lệ. "
                f"Giá trị cho phép: {', '.join(sorted(VALID_ROLES))}"
            ),
        )

    users, total = user_crud.get_users(
        db,
        role=role,
        is_active=is_active,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return UserListOut(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


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