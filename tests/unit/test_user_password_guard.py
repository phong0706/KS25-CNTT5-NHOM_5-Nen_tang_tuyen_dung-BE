"""Unit tests cho is_bcrypt_hash và chốt chặn ORM User before_insert/before_update (BUG_DB_001)."""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, is_bcrypt_hash
from app.models.user import User


def _memory_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    return Session(bind=engine)


def test_is_bcrypt_hash_validates_strictly():
    hashed = hash_password("StrongPass123!")
    assert is_bcrypt_hash(hashed) is True
    assert is_bcrypt_hash("$2a$12$" + "a" * 53) is True
    assert is_bcrypt_hash("$2y$10$" + "." * 53) is True

    assert is_bcrypt_hash(None) is False
    assert is_bcrypt_hash("") is False
    assert is_bcrypt_hash("plaintext") is False
    assert is_bcrypt_hash("hashed_password") is False
    assert is_bcrypt_hash("$2b$12$too_short") is False
    assert is_bcrypt_hash("$2b$9$invalid_cost") is False


def test_user_orm_rejects_plaintext_on_insert():
    with _memory_session() as db:
        u = User(
            email=f"plain_{uuid.uuid4().hex[:6]}@test.com",
            password="plaintext_password",
            full_name="Plain User",
            role="candidate",
        )
        db.add(u)
        with pytest.raises(ValueError, match="bcrypt"):
            db.flush()


def test_user_orm_rejects_plaintext_on_update_and_allows_valid_update():
    with _memory_session() as db:
        u = User(
            email=f"valid_{uuid.uuid4().hex[:6]}@test.com",
            password=hash_password("ValidPass123!"),
            full_name="Valid User",
            role="candidate",
        )
        db.add(u)
        db.commit()

        # Cập nhật trường khác vẫn hợp lệ
        u.token_version += 1
        db.commit()
        assert u.token_version == 2

        # Gán mật khẩu thô khi update bị chặn
        u.password = "raw_password_again"
        with pytest.raises(ValueError, match="bcrypt"):
            db.flush()
