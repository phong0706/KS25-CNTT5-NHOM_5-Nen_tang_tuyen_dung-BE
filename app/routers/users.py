"""Router quản lý người dùng (dành cho Admin)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut], summary="Danh sách người dùng (chỉ Admin)")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
    role: str | None = Query(None, description="Lọc theo role: candidate, employer, admin"),
    q: str | None = Query(None, description="Tìm kiếm theo tên hoặc email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where((User.full_name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
    stmt = stmt.order_by(User.id.desc()).offset(skip).limit(limit)
    return db.scalars(stmt).all()


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


@router.patch("/{user_id}/toggle-status", response_model=UserOut, summary="Khoá/Mở khoá tài khoản (chỉ Admin)")
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
    db.commit()
    db.refresh(user)
    return user
