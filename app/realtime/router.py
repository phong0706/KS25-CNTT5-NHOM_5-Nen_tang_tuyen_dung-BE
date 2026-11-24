"""WebSocket Endpoint /ws/notifications & REST API cấp vé POST /api/ws/ticket.

Tuân thủ techrecruit-rules: <= 200 dòng, phân quyền, kiểm tra Origin trước accept().
"""
import asyncio
import logging
import time
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from app.core.config import settings
from app.core.security import ALL_AUTHENTICATED_ROLES, role_required
from app.db.session import SessionLocal
from app.models.user import User
from app.realtime.manager import HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, manager
from app.realtime.protocol import CloseCode, build_server_message, parse_client_message
from app.realtime.tickets import ticket_store
from app.services.notification import count_unread

logger = logging.getLogger("techrecruit.realtime")
router = APIRouter(tags=["Realtime WebSocket"])


def is_allowed_origin(origin: str | None) -> bool:
    """Kiểm tra header Origin có nằm trong danh sách cho phép."""
    if not origin:
        return False
    allowed = settings.cors_origin_list
    if "*" in allowed or origin in allowed:
        return True
    try:
        p = urlparse(origin)
        if p.hostname in ("localhost", "127.0.0.1"):
            return True
    except Exception:
        pass
    return False


@router.post("/api/ws/ticket", summary="Cấp vé kết nối WebSocket dùng 1 lần (TTL 30s)")
def create_websocket_ticket(current_user: User = Depends(role_required(*ALL_AUTHENTICATED_ROLES))):
    """Cấp vé 1 lần. Chặn nếu chạy multi-worker không Redis hoặc vượt rate limit."""
    if manager.is_multi_worker_without_redis():
        return {"enabled": False, "ticket": None, "message": "Multi-worker mode without Redis: WebSocket disabled"}

    jwt_exp = time.time() + (settings.JWT_EXPIRE_MINUTES * 60)
    ticket, err = ticket_store.issue_ticket(
        user_id=current_user.id, role=current_user.role,
        token_ver=getattr(current_user, "token_version", 1), jwt_exp=jwt_exp, ttl=30.0,
    )
    if err == "RATE_LIMIT_EXCEEDED":
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Quá nhiều yêu cầu cấp vé.")
    return {"enabled": True, "ticket": ticket, "expires_in": 30}


async def _heartbeat_loop(ws: WebSocket, conn, user_id: int):
    """Gửi ping định kỳ 25s, ngắt 4408 nếu quá 60s không pong, ngắt 4401 nếu token hết hạn."""
    try:
        while not conn.is_closed:
            await asyncio.sleep(manager.heartbeat_interval)
            now = time.time()
            if now > conn.jwt_exp:
                conn.is_closed = True
                await ws.close(code=CloseCode.UNAUTHORIZED, reason="Token expired")
                break
            if now - conn.last_pong > manager.heartbeat_timeout:
                conn.is_closed = True
                await ws.close(code=CloseCode.PING_TIMEOUT, reason="Heartbeat timeout")
                break
            try:
                conn.queue.put_nowait(build_server_message("ping"))
            except Exception:
                pass
    except asyncio.CancelledError:
        pass


@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(websocket: WebSocket, ticket: str | None = Query(None)):
    """WebSocket endpoint thông báo realtime."""
    origin = websocket.headers.get("origin")
    if not is_allowed_origin(origin):
        await websocket.close(code=CloseCode.FORBIDDEN, reason="Forbidden origin")
        return

    ticket_data, err = ticket_store.consume_ticket(ticket)
    if not ticket_data:
        await websocket.close(code=CloseCode.UNAUTHORIZED, reason=f"Invalid ticket: {err}")
        return

    db = SessionLocal()
    try:
        user = db.get(User, ticket_data.user_id)
        if not user or not user.is_active or getattr(user, "token_version", 1) != ticket_data.token_ver:
            await websocket.close(code=CloseCode.FORBIDDEN, reason="Account locked or token invalid")
            return
        unread_cnt = count_unread(db, user.id)
    finally:
        db.close()

    await websocket.accept()
    conn = await manager.register(websocket, ticket_data.user_id, ticket_data.jwt_exp)
    await conn.queue.put(build_server_message("hello", {"unread_count": unread_cnt, "user_id": ticket_data.user_id}))

    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket, conn, ticket_data.user_id))
    try:
        while not conn.is_closed:
            msg_obj = await websocket.receive()
            if msg_obj["type"] == "websocket.disconnect":
                break
            if "bytes" in msg_obj and msg_obj["bytes"]:
                await websocket.close(code=CloseCode.POLICY_VIOLATION, reason="Binary not allowed")
                break
            if "text" in msg_obj:
                valid, msg_type, _, close_c = parse_client_message(msg_obj["text"])
                if not valid:
                    await websocket.close(code=close_c or CloseCode.POLICY_VIOLATION, reason="Invalid message")
                    break
                if msg_type == "pong":
                    conn.last_pong = time.time()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        heartbeat_task.cancel()
        await manager.unregister(conn)
