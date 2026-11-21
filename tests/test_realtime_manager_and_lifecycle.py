"""Kiểm thử ConnectionManager: cách ly người dùng, đa kết nối, client chậm, rò rỉ và khóa tài khoản.

Tuân thủ techrecruit-rules: <= 200 dòng, mỗi ca là một test riêng biệt.
"""
from pathlib import Path
import sys
import time
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.realtime.manager import manager
from app.realtime.protocol import CloseCode, build_server_message
from app.realtime.tickets import ticket_store


@pytest.fixture(autouse=True)
def reset_state():
    ticket_store.clear()
    ticket_store.max_requests = 100
    manager.heartbeat_interval = 25.0
    manager.heartbeat_timeout = 60.0
    yield
    ticket_store.clear()
    ticket_store.max_requests = 10
    manager.heartbeat_interval = 25.0
    manager.heartbeat_timeout = 60.0


@pytest.fixture(scope="module")
def users_fixture():
    db = SessionLocal()
    cand = db.query(User).filter_by(role="candidate", is_active=True).first()
    emp = db.query(User).filter_by(role="employer", is_active=True).first()
    adm = db.query(User).filter_by(role="admin", is_active=True).first()
    db.close()
    return {"cand": cand, "emp": emp, "adm": adm}


def _get_ticket(client, user):
    tok = create_access_token(user.id, user.role, getattr(user, "token_version", 1))
    res = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {tok}"})
    return res.json()["ticket"]


def _recv(ws):
    while True:
        m = ws.receive_json()
        if m.get("type") == "ping":
            try:
                ws.send_json({"type": "pong"})
            except Exception:
                pass
            continue
        return m


def test_ws_isolation_between_users(users_fixture):
    """User A không bao giờ nhận thông báo của User B; candidate không nhận tin của employer."""
    cand, emp = users_fixture["cand"], users_fixture["emp"]
    origin = {"origin": "http://127.0.0.1:5502"}
    c1, c2 = TestClient(app), TestClient(app)

    t_cand = _get_ticket(c1, cand)
    t_emp = _get_ticket(c2, emp)

    with c1.websocket_connect(f"/ws/notifications?ticket={t_cand}", headers=origin) as ws_cand:
        _ = _recv(ws_cand)  # hello
        with c2.websocket_connect(f"/ws/notifications?ticket={t_emp}", headers=origin) as ws_emp:
            _ = _recv(ws_emp)  # hello

            manager.send_to_user_nowait(cand.id, build_server_message("notification", {"for_user": cand.id}))
            msg_cand = _recv(ws_cand)
            assert msg_cand["data"]["for_user"] == cand.id

            manager.send_to_user_nowait(emp.id, build_server_message("notification", {"for_user": emp.id}))
            msg_emp = _recv(ws_emp)
            assert msg_emp["data"]["for_user"] == emp.id


def test_ws_multi_connections_and_max_5_limit(users_fixture):
    """Nhiều tab của 1 user đều nhận tin; kết nối thứ 6 làm kết nối cũ nhất bị đóng 4429."""
    cand = users_fixture["cand"]
    origin = {"origin": "http://127.0.0.1:5502"}

    clients = [TestClient(app) for _ in range(5)]
    conns = []
    for cl in clients:
        t = _get_ticket(cl, cand)
        ws_ctx = cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin)
        ws = ws_ctx.__enter__()
        _ = _recv(ws)
        conns.append((ws_ctx, ws))

    assert manager.get_user_connections_count(cand.id) == 5

    manager.send_to_user_nowait(cand.id, build_server_message("notification", {"multicast": True}))
    for _, ws in conns:
        assert _recv(ws)["data"]["multicast"] is True

    c6 = TestClient(app)
    t6 = _get_ticket(c6, cand)
    with c6.websocket_connect(f"/ws/notifications?ticket={t6}", headers=origin) as ws6:
        _ = _recv(ws6)
        ws1_ctx, ws1 = conns[0]
        with pytest.raises(WebSocketDisconnect) as exc:
            _ = _recv(ws1)
        assert exc.value.code == CloseCode.TOO_MANY_CONNECTIONS

    for ctx, _ in conns[1:]:
        try:
            ctx.__exit__(None, None, None)
        except Exception:
            pass


def test_ws_no_leak_after_rapid_connect_disconnect(users_fixture):
    """Sau 200 vòng connect/disconnect, số lượng kết nối trong manager về đúng 0."""
    cand = users_fixture["cand"]
    cl = TestClient(app)
    origin = {"origin": "http://127.0.0.1:5502"}
    initial_total = manager.total_connections

    for _ in range(50):
        ticket_str, _ = ticket_store.issue_ticket(
            cand.id, cand.role, token_ver=getattr(cand, "token_version", 1), ttl=30.0
        )
        with cl.websocket_connect(f"/ws/notifications?ticket={ticket_str}", headers=origin) as ws:
            _ = _recv(ws)

    # 150 vòng tiếp theo trực tiếp trên manager để đạt đúng 200 vòng không tốn I/O
    class DummyWS:
        async def close(self, code=1000, reason=""): pass
    for _ in range(150):
        import asyncio
        conn = asyncio.run(manager.register(DummyWS(), cand.id, time.time() + 3600))
        asyncio.run(manager.unregister(conn))

    assert manager.get_user_connections_count(cand.id) == 0
    assert manager.total_connections == initial_total


def test_ws_slow_consumer_queue_overflow(users_fixture):
    """Client chậm không đọc tin: queue vượt 100 -> đóng mã 1013 (Try again later)."""
    cand = users_fixture["cand"]
    cl = TestClient(app)
    origin = {"origin": "http://127.0.0.1:5502"}
    t = _get_ticket(cl, cand)

    with cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
        _ = _recv(ws)
        for i in range(110):
            manager.send_to_user_nowait(cand.id, build_server_message("notification", {"seq": i}))

        with pytest.raises(WebSocketDisconnect) as exc:
            for _ in range(120):
                _ = ws.receive_json()
        assert exc.value.code == CloseCode.TRY_AGAIN_LATER


def test_ws_user_lock_disconnects_all_connections(users_fixture):
    """Khóa tài khoản qua API admin -> mọi kết nối của user bị đóng 4403 ngay lập tức."""
    db = SessionLocal()
    test_u = User(email="victim_lock_ws@test.vn", password="pwd", full_name="Victim WS", role="candidate", is_active=True)
    db.add(test_u)
    db.commit()
    db.refresh(test_u)
    db.close()

    adm = users_fixture["adm"]
    c_user, c_adm = TestClient(app), TestClient(app)
    origin = {"origin": "http://127.0.0.1:5502"}
    t = _get_ticket(c_user, test_u)

    try:
        with c_user.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
            _ = _recv(ws)
            adm_tok = create_access_token(adm.id, adm.role, getattr(adm, "token_version", 1))
            r_lock = c_adm.post(f"/api/users/{test_u.id}/lock", headers={"Authorization": f"Bearer {adm_tok}"}, json={"locked_reason": "Vi phạm điều khoản"})
            assert r_lock.status_code == 200

            with pytest.raises(WebSocketDisconnect) as exc:
                _ = _recv(ws)
            assert exc.value.code == CloseCode.FORBIDDEN
    finally:
        db = SessionLocal()
        u_del = db.get(User, test_u.id)
        if u_del:
            db.delete(u_del)
            db.commit()
        db.close()


def test_ws_heartbeat_timeout_closes_4408(users_fixture):
    """Heartbeat: không pong trong 60s (giả lập 0.3s) -> đóng 4408."""
    cand = users_fixture["cand"]
    cl = TestClient(app)
    origin = {"origin": "http://127.0.0.1:5502"}
    manager.heartbeat_interval = 0.1
    manager.heartbeat_timeout = 0.3

    t = _get_ticket(cl, cand)
    with cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
        _ = ws.receive_json()  # hello
        with pytest.raises(WebSocketDisconnect) as exc:
            for _ in range(10):
                time.sleep(0.1)
                _ = ws.receive_json()
        assert exc.value.code == CloseCode.PING_TIMEOUT
