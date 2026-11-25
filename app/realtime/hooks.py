"""Hook SQLAlchemy đẩy sự kiện thông báo ra WebSocket SAU KHI COMMIT thành công.

Tuân thủ techrecruit-rules: <= 200 dòng, không làm hỏng giao dịch nghiệp vụ.
"""
import logging
from typing import Any
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
from app.realtime.manager import manager
from app.realtime.protocol import build_server_message

logger = logging.getLogger("techrecruit.realtime")
SESSION_PENDING_KEY = "pending_realtime_events"


def register_realtime_notification_event(session: Session, user_id: int, notif_payload: dict[str, Any]):
    """Ghi nhận sự kiện thông báo đang chờ commit trong transaction hiện tại."""
    pending = session.info.setdefault(SESSION_PENDING_KEY, [])
    pending.append((user_id, notif_payload))


def dispatch_realtime_event_safely(user_id: int, notif_payload: dict[str, Any]):
    """Đẩy tin nhắn tới client qua WebSocket an toàn (không bao giờ throw exception)."""
    try:
        msg = build_server_message("notification", notif_payload, msg_id=notif_payload.get("id"))
        manager.send_to_user_nowait(user_id, msg)
    except Exception as e:
        logger.warning("Không thể phát sự kiện realtime tới user %s: %s", user_id, e)


def setup_sqlalchemy_realtime_hooks():
    """Đăng ký hook after_commit và after_rollback cho SQLAlchemy Session."""
    @event.listens_for(Session, "after_commit")
    def _handle_after_commit(session: Session):
        events = session.info.pop(SESSION_PENDING_KEY, None)
        if not events:
            return
        for user_id, payload in events:
            dispatch_realtime_event_safely(user_id, payload)

    @event.listens_for(Session, "after_rollback")
    def _handle_after_rollback(session: Session):
        session.info.pop(SESSION_PENDING_KEY, None)


# Khởi tạo hook khi import module
setup_sqlalchemy_realtime_hooks()
