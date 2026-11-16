"""CRUD cho bảng users."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    full_name: str,
    phone: str | None,
    role: str,
) -> User:
    user = User(
        email=email,
        password=hashed_password,
        full_name=full_name,
        phone=phone,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_users(
    db: Session,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """Lọc theo role / is_active, tìm kiếm email - họ tên - phone, phân trang.

    Returns:
        (danh_sách_user_trang_hiện_tại, tổng_số_user_thoả_mãn)
    """
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.where(
            or_(
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
                User.phone.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    query = (
        query.order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = list(db.scalars(query))
    return users, int(total or 0)


def lock_user(db: Session, *, user: User, locked_reason: str) -> User:
    """Khoá tài khoản: is_active=False + lưu lý do khoá."""
    user.is_active = False
    user.locked_reason = locked_reason
    db.commit()
    db.refresh(user)
    return user


def unlock_user(db: Session, *, user: User) -> User:
    """Mở khoá tài khoản: is_active=True + xoá lý do khoá."""
    user.is_active = True
    user.locked_reason = None
    db.commit()
    db.refresh(user)
    return user
