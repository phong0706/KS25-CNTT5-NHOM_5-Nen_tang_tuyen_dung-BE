"""Quản lý vé kết nối một lần (One-Time Ticket) và giới hạn tần suất cấp vé.

Tuân thủ techrecruit-rules: thuần logic, không I/O, <= 200 dòng.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import secrets
import time


@dataclass
class TicketData:
    ticket: str
    user_id: int
    role: str
    token_ver: int
    jwt_exp: float
    created_at: float
    ttl: float = 30.0

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.created_at + self.ttl)

    @property
    def is_jwt_expired(self) -> bool:
        return time.time() > self.jwt_exp


class TicketStore:
    """Lưu trữ vé kết nối dùng 1 lần trong bộ nhớ kèm rate limiter."""

    def __init__(self, default_ttl: float = 30.0, rate_limit_window: float = 60.0, max_requests: int = 10):
        self._tickets: dict[str, TicketData] = {}
        self._user_req_times: dict[int, list[float]] = {}
        self.default_ttl = default_ttl
        self.rate_limit_window = rate_limit_window
        self.max_requests = max_requests

    def check_rate_limit(self, user_id: int) -> bool:
        """Kiểm tra giới hạn cấp vé (tối đa max_requests vé trong window giây)."""
        now = time.time()
        times = [t for t in self._user_req_times.get(user_id, []) if now - t < self.rate_limit_window]
        self._user_req_times[user_id] = times
        if len(times) >= self.max_requests:
            return False
        times.append(now)
        self._user_req_times[user_id] = times
        return True

    def issue_ticket(
        self,
        user_id: int,
        role: str,
        token_ver: int = 1,
        jwt_exp: float | None = None,
        ttl: float | None = None,
    ) -> tuple[str | None, str | None]:
        """Cấp vé mới dùng 1 lần. Trả về (ticket, error_code)."""
        if not self.check_rate_limit(user_id):
            return None, "RATE_LIMIT_EXCEEDED"

        self.cleanup_expired()
        ticket_str = secrets.token_urlsafe(32)
        exp_time = jwt_exp if jwt_exp is not None else (time.time() + 86400.0)
        data = TicketData(
            ticket=ticket_str,
            user_id=user_id,
            role=role,
            token_ver=token_ver,
            jwt_exp=exp_time,
            created_at=time.time(),
            ttl=ttl or self.default_ttl,
        )
        self._tickets[ticket_str] = data
        return ticket_str, None

    def consume_ticket(self, ticket_str: str | None) -> tuple[TicketData | None, str | None]:
        """Sử dụng vé đúng một lần. Nếu hợp lệ, xóa vé ngay và trả về TicketData."""
        if not ticket_str:
            return None, "MISSING_TICKET"

        data = self._tickets.pop(ticket_str, None)
        if not data:
            return None, "INVALID_OR_ALREADY_USED"

        if data.is_expired:
            return None, "TICKET_EXPIRED"

        if data.is_jwt_expired:
            return None, "TOKEN_EXPIRED"

        return data, None

    def revoke_user_tickets(self, user_id: int) -> int:
        """Hủy toàn bộ vé của user khi bị khóa hoặc đổi vai trò."""
        to_del = [t for t, d in self._tickets.items() if d.user_id == user_id]
        for t in to_del:
            self._tickets.pop(t, None)
        return len(to_del)

    def cleanup_expired(self) -> int:
        """Dọn dẹp các vé đã quá hạn TTL."""
        now = time.time()
        expired = [t for t, d in self._tickets.items() if now > (d.created_at + d.ttl)]
        for t in expired:
            self._tickets.pop(t, None)
        return len(expired)

    def clear(self) -> None:
        """Xóa sạch toàn bộ vé và lịch sử rate limit (phục vụ test)."""
        self._tickets.clear()
        self._user_req_times.clear()


ticket_store = TicketStore()
