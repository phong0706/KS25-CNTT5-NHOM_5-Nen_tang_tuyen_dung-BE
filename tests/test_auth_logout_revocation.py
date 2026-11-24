"""Kiểm thử thu hồi JWT khi đăng xuất và khóa tài khoản (BUG_AUTH_001)."""
import uuid

from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)


def _create_temp_user(role: str = "candidate") -> tuple[int, str, str]:
    email = f"logout_test_{uuid.uuid4().hex[:8]}@test.vn"
    pw = "StrongPass123!"
    db = SessionLocal()
    try:
        u = User(
            email=email,
            password=hash_password(pw),
            full_name="Logout Test User",
            role=role,
            is_active=True,
            token_version=1,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id, email, pw
    finally:
        db.close()


def _cleanup_user(uid: int) -> None:
    db = SessionLocal()
    try:
        u = db.get(User, uid)
        if u:
            db.delete(u)
            db.commit()
    finally:
        db.close()


def test_logout_revokes_jwt_and_allows_relogin():
    uid, email, pw = _create_temp_user()
    try:
        # Chưa đăng nhập gọi /logout -> 401
        r_noauth = client.post("/api/auth/logout")
        assert r_noauth.status_code == 401

        # Đăng nhập lấy JWT
        r_login = client.post("/api/auth/login", json={"email": email, "password": pw})
        assert r_login.status_code == 200
        token1 = r_login.json()["access_token"]
        h1 = {"Authorization": f"Bearer {token1}"}

        assert client.get("/api/auth/me", headers=h1).status_code == 200

        # Đăng xuất -> 200
        r_logout = client.post("/api/auth/logout", headers=h1)
        assert r_logout.status_code == 200

        # Token cũ bị từ chối ở /me, /logout và /ws/ticket
        assert client.get("/api/auth/me", headers=h1).status_code == 401
        assert client.post("/api/auth/logout", headers=h1).status_code == 401
        assert client.post("/api/ws/ticket", headers=h1).status_code == 401

        # Đăng nhập lại lấy JWT mới -> hoạt động bình thường
        r_login2 = client.post("/api/auth/login", json={"email": email, "password": pw})
        assert r_login2.status_code == 200
        token2 = r_login2.json()["access_token"]
        assert token2 != token1
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token2}"}).status_code == 200
    finally:
        _cleanup_user(uid)


def test_token_without_token_ver_claim_is_rejected():
    uid, _, _ = _create_temp_user()
    try:
        forged_no_tv = jwt.encode(
            {"sub": str(uid), "role": "candidate"},
            settings.JWT_SECRET,
            algorithm=ALGORITHM,
        )
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_no_tv}"})
        assert res.status_code == 401
    finally:
        _cleanup_user(uid)


def test_create_access_token_includes_jti_and_token_ver():
    tok = create_access_token(user_id=1, role="candidate", token_version=3)
    payload = jwt.decode(tok, settings.JWT_SECRET, algorithms=[ALGORITHM])
    assert payload["sub"] == "1"
    assert payload["token_ver"] == 3
    assert isinstance(payload.get("jti"), str) and len(payload["jti"]) >= 16
