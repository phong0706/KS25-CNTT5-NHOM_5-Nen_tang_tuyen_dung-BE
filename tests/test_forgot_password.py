"""Test suite cho tính năng Quên mật khẩu và Đặt lại mật khẩu."""
import hashlib, os, sys
from datetime import datetime, timedelta

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from fastapi.testclient import TestClient
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.password_reset import PasswordResetToken
from app.models.user import User

client = TestClient(app)
TEST_EMAIL = "test_forgot_pw_user@example.com"


def setup_module():
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    if not user:
        user = User(email=TEST_EMAIL, password=hash_password("OldPassword123@"), full_name="User Quên PW", role="candidate", token_version=1, is_active=True)
        db.add(user)
    else:
        user.password = hash_password("OldPassword123@")
        user.token_version = 1
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    db.commit()
    db.close()


def teardown_module():
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    if user:
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
        db.delete(user)
        db.commit()
    db.close()


def test_account_enumeration_protection():
    res = client.post("/api/auth/forgot-password", json={"email": "non_existent_999@domain.com"})
    assert res.status_code == 200
    assert "Nếu email của bạn tồn tại" in res.json()["message"]


def test_request_code_and_hash_storage():
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    db.commit()
    db.close()

    res = client.post("/api/auth/forgot-password", json={"email": TEST_EMAIL})
    assert res.status_code == 200
    assert "Nếu email của bạn tồn tại" in res.json()["message"]

    db = SessionLocal()
    token = db.query(PasswordResetToken).join(User).filter(User.email == TEST_EMAIL).order_by(PasswordResetToken.created_at.desc()).first()
    assert token is not None and len(token.token_hash) == 64 and not token.token_hash.isdigit()
    db.close()


def test_request_code_rate_limit_cooldown():
    res = client.post("/api/auth/forgot-password", json={"email": TEST_EMAIL})
    assert res.status_code == 429
    assert res.json()["detail"].get("code") == "RATE_LIMITED"


def test_reset_password_weak_password():
    res = client.post("/api/auth/reset-password", json={"email": TEST_EMAIL, "code": "123456", "new_password": "123"})
    assert res.status_code in (400, 422)


def test_reset_password_wrong_code_and_attempt_limit():
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    user_id = user.id
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete()
    dummy_code = "654321"
    token = PasswordResetToken(user_id=user_id, token_hash=hashlib.sha256(dummy_code.encode()).hexdigest(), expires_at=datetime.utcnow() + timedelta(minutes=15))
    db.add(token)
    db.commit()
    db.close()

    res = client.post("/api/auth/reset-password", json={"email": TEST_EMAIL, "code": "000000", "new_password": "NewValidPass123@"})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_CODE"

    db = SessionLocal()
    t = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).first()
    t.attempts = 5
    db.commit()
    db.close()

    res2 = client.post("/api/auth/reset-password", json={"email": TEST_EMAIL, "code": "000000", "new_password": "NewValidPass123@"})
    assert res2.status_code == 400
    assert res2.json()["detail"]["code"] == "TOO_MANY_ATTEMPTS"


def test_reset_password_expired_token():
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    valid_code = "777888"
    token = PasswordResetToken(user_id=user.id, token_hash=hashlib.sha256(valid_code.encode()).hexdigest(), expires_at=datetime.utcnow() - timedelta(minutes=1))
    db.add(token)
    db.commit()
    db.close()

    res = client.post("/api/auth/reset-password", json={"email": TEST_EMAIL, "code": valid_code, "new_password": "NewValidPass123@"})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "CODE_EXPIRED"


def test_reset_password_success_and_session_revocation():
    db = SessionLocal()
    user = db.query(User).filter(User.email == TEST_EMAIL).first()
    user.password = hash_password("PreResetPass123@")
    user.token_version = 1
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()

    valid_code = "888999"
    token = PasswordResetToken(user_id=user.id, token_hash=hashlib.sha256(valid_code.encode()).hexdigest(), expires_at=datetime.utcnow() + timedelta(minutes=15))
    db.add(token)
    db.commit()
    db.close()

    login_res = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "PreResetPass123@"})
    assert login_res.status_code == 200
    old_jwt = login_res.json()["access_token"]

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_jwt}"})
    assert me_res.status_code == 200

    new_pw = "NewSecretPassword2026@"
    reset_res = client.post("/api/auth/reset-password", json={"email": TEST_EMAIL, "code": valid_code, "new_password": new_pw})
    assert reset_res.status_code == 200

    # Old JWT must now fail with 401
    me_revoked = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_jwt}"})
    assert me_revoked.status_code == 401

    # Single-use check: reusing same code fails
    reuse_res = client.post("/api/auth/reset-password", json={"email": TEST_EMAIL, "code": valid_code, "new_password": "AnotherPassword123@"})
    assert reuse_res.status_code == 400

    # Login with new password succeeds
    new_login = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": new_pw})
    assert new_login.status_code == 200
