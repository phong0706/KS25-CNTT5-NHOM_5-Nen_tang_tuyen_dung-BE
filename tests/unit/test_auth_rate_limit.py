"""Unit test kiểm thử cơ chế Rate Limiting chống Brute-force & Credential Stuffing (SEC-01)."""
from app.core.rate_limit import AuthRateLimiter

def test_login_rate_limiter_blocks_after_max_email_attempts():
    limiter = AuthRateLimiter(max_ip_attempts=20, max_email_attempts=3, window_seconds=60.0)
    # Tắt cờ bypass testing để test logic limiter
    limiter._is_testing = lambda: False

    email = "victim@example.com"
    ip = "192.168.1.100"

    # 3 lần thử sai liên tiếp
    for _ in range(3):
        allowed, _ = limiter.check_login_allowed(ip, email)
        assert allowed is True
        limiter.record_login_failure(ip, email)

    # Lần thứ 4 phải bị chặn (429)
    allowed, retry_after = limiter.check_login_allowed(ip, email)
    assert allowed is False
    assert retry_after > 0

def test_login_rate_limiter_blocks_ip_brute_force():
    limiter = AuthRateLimiter(max_ip_attempts=5, max_email_attempts=10, window_seconds=60.0)
    limiter._is_testing = lambda: False

    ip = "10.0.0.99"
    # Thử nhiều email khác nhau từ cùng 1 IP
    for i in range(5):
        allowed, _ = limiter.check_login_allowed(ip, f"user{i}@example.com")
        assert allowed is True
        limiter.record_login_failure(ip, f"user{i}@example.com")

    # IP bị chặn sau 5 lần thử sai
    allowed, retry_after = limiter.check_login_allowed(ip, "another@example.com")
    assert allowed is False
    assert retry_after > 0

def test_login_success_clears_email_lockout():
    limiter = AuthRateLimiter(max_ip_attempts=20, max_email_attempts=3, window_seconds=60.0)
    limiter._is_testing = lambda: False

    email = "user@example.com"
    ip = "192.168.1.1"

    # 2 lần sai
    for _ in range(2):
        limiter.record_login_failure(ip, email)

    # Đăng nhập đúng -> xóa lịch sử vi phạm
    limiter.record_login_success(ip, email)

    # Thêm 2 lần sai nữa vẫn chưa đạt ngưỡng 3
    for _ in range(2):
        allowed, _ = limiter.check_login_allowed(ip, email)
        assert allowed is True
        limiter.record_login_failure(ip, email)

def test_reset_password_rate_limiter():
    limiter = AuthRateLimiter(window_seconds=60.0)
    limiter._is_testing = lambda: False

    ip = "192.168.1.50"
    for _ in range(5):
        allowed, _ = limiter.check_reset_password_allowed(ip, max_requests=5)
        assert allowed is True

    # Quá 5 lần gọi thử OTP -> bị chặn
    allowed, retry_after = limiter.check_reset_password_allowed(ip, max_requests=5)
    assert allowed is False
    assert retry_after > 0
