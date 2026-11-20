"""Định nghĩa giao thức JSON có phiên bản (v=1) và mã đóng WebSocket.

Tuân thủ techrecruit-rules: thuần logic, không I/O, <= 200 dòng.
"""
from datetime import datetime, timezone
from enum import IntEnum
import json
from typing import Any


class CloseCode(IntEnum):
    NORMAL_CLOSURE = 1000
    POLICY_VIOLATION = 1008
    MESSAGE_TOO_BIG = 1009
    SERVICE_RESTART = 1012
    TRY_AGAIN_LATER = 1013
    UNAUTHORIZED = 4401
    FORBIDDEN = 4403
    PING_TIMEOUT = 4408
    TOO_MANY_CONNECTIONS = 4429


PROTOCOL_VERSION = 1
MAX_CLIENT_MSG_BYTES = 1024
ALLOWED_CLIENT_TYPES = {"pong", "ack"}


def build_server_message(
    msg_type: str,
    data: dict[str, Any] | None = None,
    msg_id: str | int | None = None,
) -> dict[str, Any]:
    """Tạo cấu trúc tin nhắn chuẩn từ server gửi client."""
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "v": PROTOCOL_VERSION,
        "type": msg_type,
        "id": msg_id,
        "ts": now_iso,
        "data": data or {},
    }


def serialize_realtime_notification(
    notif: Any,
    unread_count: int,
    actor_name: str | None = None,
    title: str | None = None,
    body: str | None = None,
    href: str | None = None,
) -> dict[str, Any]:
    """Serialize thông báo realtime dùng chung schema với NotificationOut."""
    t = title or getattr(notif, "title", "") or ""
    b = body or getattr(notif, "message", "") or ""
    h = href or getattr(notif, "link", "") or ""
    created_at = getattr(notif, "created_at", None)
    if isinstance(created_at, datetime):
        c_iso = created_at.isoformat()
    elif created_at:
        c_iso = str(created_at)
    else:
        c_iso = datetime.now(timezone.utc).isoformat()

    r_at = getattr(notif, "read_at", None)
    r_iso = r_at.isoformat() if isinstance(r_at, datetime) else (str(r_at) if r_at else None)
    is_read = bool(getattr(notif, "is_read", False) or r_at is not None)

    return {
        "id": int(getattr(notif, "id", 0)),
        "type": getattr(notif, "type", "") or getattr(notif, "notification_type", "") or "system",
        "title": t,
        "body": b,
        "href": h,
        "created_at": c_iso,
        "read": is_read,
        "is_read": is_read,
        "read_at": r_iso,
        "message": b,
        "link": h,
        "ref_type": getattr(notif, "ref_type", None) or getattr(notif, "entity_type", None),
        "ref_id": getattr(notif, "ref_id", None) or getattr(notif, "entity_id", None),
        "actor_id": getattr(notif, "actor_id", None),
        "actor_name": actor_name,
        "unread_count": int(unread_count),
    }


def parse_client_message(raw: str | bytes) -> tuple[bool, str | None, dict[str, Any] | None, int | None]:
    """Phân tích và kiểm tra tính hợp lệ của tin nhắn từ client gửi lên.

    Trả về: (hợp lệ, kiểu tin, dữ liệu, mã lỗi đóng nếu có)
    """
    if isinstance(raw, bytes):
        if len(raw) > MAX_CLIENT_MSG_BYTES:
            return False, None, None, CloseCode.MESSAGE_TOO_BIG
        try:
            raw_text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return False, None, None, CloseCode.POLICY_VIOLATION
    else:
        raw_text = raw
        if len(raw_text.encode("utf-8")) > MAX_CLIENT_MSG_BYTES:
            return False, None, None, CloseCode.MESSAGE_TOO_BIG

    try:
        data = json.loads(raw_text)
    except Exception:
        return False, None, None, CloseCode.POLICY_VIOLATION

    if not isinstance(data, dict):
        return False, None, None, CloseCode.POLICY_VIOLATION

    msg_type = data.get("type")
    if not isinstance(msg_type, str) or msg_type not in ALLOWED_CLIENT_TYPES:
        return False, None, None, CloseCode.POLICY_VIOLATION

    return True, msg_type, data, None
