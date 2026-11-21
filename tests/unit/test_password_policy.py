"""Unit test kiểm thử chính sách độ mạnh mật khẩu OWASP (SEC-02)."""
import pytest
from pydantic import ValidationError
from app.schemas.auth import RegisterRequest, ResetPasswordRequest, validate_password_strength

def test_validate_password_strength_accepts_strong_passwords():
    valid = ["P@ssw0rd123", "StrongPass2026", "Abcd1234#", "TuyenDung2026!"]
    for pw in valid:
        assert validate_password_strength(pw) == pw

def test_validate_password_strength_rejects_weak_passwords():
    # Quá ngắn (< 8 ký tự)
    with pytest.raises(ValueError, match="ít nhất 8 ký tự"):
        validate_password_strength("123456")

    with pytest.raises(ValueError, match="ít nhất 8 ký tự"):
        validate_password_strength("Short1")

    # Chỉ có chữ
    with pytest.raises(ValueError, match="ít nhất một chữ cái và một chữ số"):
        validate_password_strength("aaaaaaaaa")

    # Chỉ có số (không nằm trong blacklist)
    with pytest.raises(ValueError, match="ít nhất một chữ cái và một chữ số"):
        validate_password_strength("9876543210123")

    # Mật khẩu phổ biến nằm trong blacklist
    with pytest.raises(ValueError, match="quá đơn giản"):
        validate_password_strength("password123")

def test_register_request_enforces_password_strength():
    # Thử đăng ký với mật khẩu yếu -> ValidationError
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="test@example.com",
            password="123",
            full_name="Test User",
            role="candidate"
        )

    # Thử với mật khẩu hợp lệ -> thành công
    req = RegisterRequest(
        email="test@example.com",
        password="SecurePass2026!",
        full_name="Test User",
        role="candidate"
    )
    assert req.password == "SecurePass2026!"
