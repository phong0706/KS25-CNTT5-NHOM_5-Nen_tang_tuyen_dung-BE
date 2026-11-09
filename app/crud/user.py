"""CRUD cho bảng users."""
from sqlalchemy import select
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
