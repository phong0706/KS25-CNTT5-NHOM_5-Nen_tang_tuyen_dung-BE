"""Unit test phòng chống lỗ hổng bypass mật khẩu plaintext (SEC-CRIT-01)."""
import pytest
from app.core.security import verify_password, hash_password

def test_verify_password_rejects_plaintext_fallback():
    """Mật khẩu lưu dạng plaintext không được chấp nhận đăng nhập."""
    assert not verify_password("hr4@", "hr4@")
    assert not verify_password("admin123", "admin123")
    assert not verify_password("123456", "123456")

def test_verify_password_rejects_invalid_and_empty_hashes():
    """Hash rỗng, hash MD5/SHA hoặc format không hợp lệ phải bị từ chối ngay."""
    assert not verify_password("", "")
    assert not verify_password("password", "")
    assert not verify_password("password", "e10adc3949ba59abbe56e057f20f883e")
    assert not verify_password("password", "sha256$randomsalt$hash")

def test_verify_password_works_with_valid_bcrypt():
    """Bcrypt hash hợp lệ ($2b$) phải hoạt động chính xác."""
    pw = "SuperSecretPassword123!"
    hashed = hash_password(pw)
    assert hashed.startswith(("$2a$", "$2b$", "$2y$"))
    assert verify_password(pw, hashed)
    assert not verify_password("WrongPassword123!", hashed)
