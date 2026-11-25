"""Quản lý danh sách kết nối WebSocket, hàng đợi gửi tin bounded và heartbeat.

Tuân thủ techrecruit-rules: <= 200 dòng, không block luồng chính.
"""
import asyncio
import logging
import os
import time
from typing import Any
from fastapi import WebSocket
from app.realtime.protocol import CloseCode, build_server_message

logger = logging.getLogger("techrecruit.realtime")

MAX_CONNECTIONS_PER_USER = 5
MAX_QUEUE_PER_CONN = 100
HEARTBEAT_INTERVAL = 25.0
HEARTBEAT_TIMEOUT = 60.0


class WebSocketConnection:
    """Đại diện cho 1 tab/kết nối của người dùng."""

    def __init__(self, ws: WebSocket, user_id: int, jwt_exp: float):
        self.ws = ws
        self.user_id = user_id
        self.jwt_exp = jwt_exp
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=MAX_QUEUE_PER_CONN)
        self.created_at = time.time()
        self.last_pong = time.time()
        self.sender_task: asyncio.Task | None = None
        self.is_closed = False

    async def send_worker(self):
        """Worker độc lập đọc tin từ queue và đẩy ra WebSocket."""
        try:
            while not self.is_closed:
                msg = await self.queue.get()
                if msg is None:
                    break
                await self.ws.send_json(msg)
                self.queue.task_done()
        except Exception as e:
            logger.debug("Lỗi gửi tin WebSocket tới user %s: %s", self.user_id, e)
        finally:
            self.is_closed = True


class ConnectionManager:
    """Quản lý các kết nối WebSocket tập trung theo user_id."""

    def __init__(self):
        self._user_conns: dict[int, list[WebSocketConnection]] = {}
        self._lock = asyncio.Lock()
        self.heartbeat_interval = HEARTBEAT_INTERVAL
        self.heartbeat_timeout = HEARTBEAT_TIMEOUT

    @property
    def total_connections(self) -> int:
        return sum(len(c_list) for c_list in self._user_conns.values())

    def get_user_connections_count(self, user_id: int) -> int:
        return len(self._user_conns.get(user_id, []))

    async def register(self, ws: WebSocket, user_id: int, jwt_exp: float) -> WebSocketConnection:
        """Đăng ký kết nối mới. Nếu vượt quá 5 kết nối, đóng kết nối cũ nhất."""
        conn = WebSocketConnection(ws, user_id, jwt_exp)
        async with self._lock:
            user_list = self._user_conns.setdefault(user_id, [])
            if len(user_list) >= MAX_CONNECTIONS_PER_USER:
                oldest = user_list.pop(0)
                try:
                    await oldest.ws.close(code=CloseCode.TOO_MANY_CONNECTIONS, reason="Max connections exceeded")
                except Exception:
                    pass
                oldest.is_closed = True
                if oldest.sender_task:
                    oldest.sender_task.cancel()

            user_list.append(conn)
            conn.sender_task = asyncio.create_task(conn.send_worker())
        return conn

    async def unregister(self, conn: WebSocketConnection):
        """Hủy đăng ký và giải phóng tài nguyên của kết nối."""
        conn.is_closed = True
        if conn.sender_task:
            conn.sender_task.cancel()
        async with self._lock:
            user_list = self._user_conns.get(conn.user_id, [])
            if conn in user_list:
                user_list.remove(conn)
            if not user_list:
                self._user_conns.pop(conn.user_id, None)

    async def disconnect_user(self, user_id: int, code: int = CloseCode.FORBIDDEN, reason: str = "Disconnected"):
        """Đóng toàn bộ kết nối của 1 user (ví dụ khi bị khóa)."""
        async with self._lock:
            conns = list(self._user_conns.pop(user_id, []))
        for c in conns:
            c.is_closed = True
            if c.sender_task:
                c.sender_task.cancel()
            try:
                await c.ws.close(code=code, reason=reason)
            except Exception:
                pass

    def send_to_user_nowait(self, user_id: int, message: dict[str, Any]) -> int:
        """Đẩy tin nhắn vào queue của tất cả kết nối thuộc user_id.

        Nếu queue đầy (> 100), đóng kết nối với mã 1013 (Client slow).
        """
        conns = list(self._user_conns.get(user_id, []))
        delivered = 0
        for c in conns:
            if c.is_closed:
                continue
            try:
                c.queue.put_nowait(message)
                delivered += 1
            except asyncio.QueueFull:
                logger.warning("Queue đầy cho user %s, đóng kết nối 1013 (Slow consumer)", user_id)
                c.is_closed = True
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._close_slow_conn(c))
                except RuntimeError:
                    try:
                        asyncio.run(self._close_slow_conn(c))
                    except Exception:
                        pass
        return delivered

    async def _close_slow_conn(self, conn: WebSocketConnection):
        await self.unregister(conn)
        try:
            await conn.ws.close(code=CloseCode.TRY_AGAIN_LATER, reason="Queue full")
        except Exception:
            pass

    async def broadcast_all(self, message: dict[str, Any]):
        """Phát tin nhắn tới toàn bộ kết nối (ví dụ close_soon khi server tắt)."""
        async with self._lock:
            all_conns = [c for c_list in self._user_conns.values() for c in c_list]
        for c in all_conns:
            if not c.is_closed:
                try:
                    c.queue.put_nowait(message)
                except Exception:
                    pass

    async def close_all_shutdown(self):
        """Gửi close_soon và đóng tất cả kết nối mã 1012 khi lifespan shutdown."""
        await self.broadcast_all(build_server_message("close_soon", {"message": "Server restarting"}))
        await asyncio.sleep(0.05)
        async with self._lock:
            all_conns = [c for c_list in self._user_conns.values() for c in c_list]
            self._user_conns.clear()
        for c in all_conns:
            c.is_closed = True
            if c.sender_task:
                c.sender_task.cancel()
            try:
                await c.ws.close(code=CloseCode.SERVICE_RESTART, reason="Server shutting down")
            except Exception:
                pass

    @staticmethod
    def is_multi_worker_without_redis() -> bool:
        """Kiểm tra nếu hệ thống chạy multi-worker nhưng không có Redis pub/sub."""
        workers = int(os.environ.get("WEB_CONCURRENCY", "1") or "1")
        has_redis = bool(os.environ.get("REDIS_URL", "").strip())
        return workers > 1 and not has_redis


manager = ConnectionManager()
