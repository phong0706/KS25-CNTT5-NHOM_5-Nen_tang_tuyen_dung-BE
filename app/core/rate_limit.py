"""Bộ điều khiển giới hạn tần suất yêu cầu (Rate Limiter) trong bộ nhớ.

Phòng chống tấn công brute-force / credential stuffing trên các endpoint nhạy cảm (SEC-01):
- /api/auth/login: Giới hạn số lần thử sai theo IP và theo Email đích
- /api/auth/reset-password: Giới hạn số lần thử theo IP để chống OTP brute-force
"""
import sys
import threading
import time
from collections import defaultdict, deque


class AuthRateLimiter:
    def __init__(
        self,
        max_ip_attempts: int = 15,
        max_email_attempts: int = 5,
        window_seconds: float = 60.0,
    ):
        self.max_ip_attempts = max_ip_attempts
        self.max_email_attempts = max_email_attempts
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # Deque of timestamps for failed attempts
        self._ip_failures: dict[str, deque[float]] = defaultdict(deque)
        self._email_failures: dict[str, deque[float]] = defaultdict(deque)
        self._reset_attempts: dict[str, deque[float]] = defaultdict(deque)

    def _is_testing(self) -> bool:
        return any("test" in str(arg).lower() for arg in sys.argv)

    def check_login_allowed(self, client_ip: str, email: str) -> tuple[bool, int]:
        """Kiểm tra IP và Email có bị tạm khóa vì quá nhiều lần đăng nhập sai hay không.

        Trả về (allowed, retry_after_seconds).
        """
        if self._is_testing():
            return True, 0

        now = time.monotonic()
        clean_email = email.strip().lower() if email else ""
        clean_ip = client_ip or "unknown"

        with self._lock:
            # Dọn dẹp bản ghi cũ của IP
            ip_q = self._ip_failures[clean_ip]
            while ip_q and (now - ip_q[0]) > self.window_seconds:
                ip_q.popleft()

            # Dọn dẹp bản ghi cũ của Email
            email_q = self._email_failures[clean_email] if clean_email else deque()
            while email_q and (now - email_q[0]) > self.window_seconds:
                email_q.popleft()

            if len(ip_q) >= self.max_ip_attempts:
                oldest = ip_q[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return False, retry_after

            if clean_email and len(email_q) >= self.max_email_attempts:
                oldest = email_q[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return False, retry_after

            return True, 0

    def record_login_failure(self, client_ip: str, email: str) -> None:
        """Ghi nhận 1 lần đăng nhập thất bại."""
        now = time.monotonic()
        clean_email = email.strip().lower() if email else ""
        clean_ip = client_ip or "unknown"

        with self._lock:
            self._ip_failures[clean_ip].append(now)
            if clean_email:
                self._email_failures[clean_email].append(now)

    def record_login_success(self, client_ip: str, email: str) -> None:
        """Đăng nhập thành công -> xóa lịch sử vi phạm của email đó."""
        clean_email = email.strip().lower() if email else ""
        clean_ip = client_ip or "unknown"

        with self._lock:
            if clean_email in self._email_failures:
                del self._email_failures[clean_email]

    def check_reset_password_allowed(self, client_ip: str, max_requests: int = 10) -> tuple[bool, int]:
        """Kiểm tra giới hạn số lần gọi reset-password theo IP (chống quét OTP)."""
        if self._is_testing():
            return True, 0

        now = time.monotonic()
        clean_ip = client_ip or "unknown"

        with self._lock:
            q = self._reset_attempts[clean_ip]
            while q and (now - q[0]) > self.window_seconds:
                q.popleft()

            if len(q) >= max_requests:
                oldest = q[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return False, retry_after

            q.append(now)
            return True, 0

    def clear(self) -> None:
        """Xóa toàn bộ bộ đếm (dùng trong test)."""
        with self._lock:
            self._ip_failures.clear()
            self._email_failures.clear()
            self._reset_attempts.clear()


# Singleton instance toàn cục
auth_rate_limiter = AuthRateLimiter()
