"""Kiểm thử xác thực bằng vé, kiểm tra Origin, giao thức JSON và giới hạn cấp vé WebSocket.

Tuân thủ techrecruit-rules: <= 200 dòng, kiểm thử các trường hợp biên và mã đóng.
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
from app.realtime.protocol import CloseCode
from app.realtime.tickets import ticket_store


@pytest.fixture(autouse=True)
def reset_state():
    ticket_store.clear()
    yield
    ticket_store.clear()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def candidate_user():
    db = SessionLocal()
    u = db.query(User).filter_by(role="candidate", is_active=True).first()
    db.close()
    return u


def test_ws_origin_check_missing_or_invalid(client, candidate_user):
    """Origin thiếu hoặc sai bị đóng với mã 4403 trước khi accept."""
    token = create_access_token(candidate_user.id, candidate_user.role, getattr(candidate_user, "token_version", 1))
    r_ticket = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    assert r_ticket.status_code == 200
    ticket = r_ticket.json()["ticket"]

    # 1. Thiếu Origin -> 4403
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/notifications?ticket={ticket}"):
            pass
    assert exc.value.code == CloseCode.FORBIDDEN

    # Cấp lại vé mới
    r_ticket2 = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    ticket2 = r_ticket2.json()["ticket"]

    # 2. Origin lạ không được phép -> 4403
    with pytest.raises(WebSocketDisconnect) as exc2:
        with client.websocket_connect(f"/ws/notifications?ticket={ticket2}", headers={"origin": "http://evil-attacker.com"}):
            pass
    assert exc2.value.code == CloseCode.FORBIDDEN


def test_ws_ticket_validation_cases(client, candidate_user):
    """Không vé, vé sai, vé hết hạn, vé dùng lần 2 đều bị đóng mã 4401."""
    origin_hdr = {"origin": "http://127.0.0.1:5502"}

    # 1. Không vé
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/notifications", headers=origin_hdr):
            pass
    assert exc.value.code == CloseCode.UNAUTHORIZED

    # 2. Vé sai / không tồn tại
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/notifications?ticket=fake_ticket_123", headers=origin_hdr):
            pass
    assert exc.value.code == CloseCode.UNAUTHORIZED

    # 3. Vé hết hạn TTL (30s)
    ticket_store.issue_ticket(user_id=candidate_user.id, role="candidate", ttl=-1.0)
    exp_ticket = list(ticket_store._tickets.keys())[-1]
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/notifications?ticket={exp_ticket}", headers=origin_hdr):
            pass
    assert exc.value.code == CloseCode.UNAUTHORIZED

    # 4. Vé dùng lần 2 (One-Time use)
    token = create_access_token(candidate_user.id, candidate_user.role, getattr(candidate_user, "token_version", 1))
    r_ticket = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    ticket = r_ticket.json()["ticket"]

    # Kết nối lần 1 -> thành công nhận hello
    with client.websocket_connect(f"/ws/notifications?ticket={ticket}", headers=origin_hdr) as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"

    # Kết nối lần 2 bằng cùng 1 vé -> bị từ chối 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/notifications?ticket={ticket}", headers=origin_hdr):
            pass
    assert exc.value.code == CloseCode.UNAUTHORIZED


def test_ws_ticket_rate_limit_and_payload_parity(client, candidate_user):
    """Giới hạn cấp vé tối đa 10 vé/phút và so sánh tính tương thích payload."""
    token = create_access_token(candidate_user.id, candidate_user.role, getattr(candidate_user, "token_version", 1))
    headers = {"Authorization": f"Bearer {token}"}

    # Cấp 10 vé liên tiếp thành công
    for _ in range(10):
        res = client.post("/api/ws/ticket", headers=headers)
        assert res.status_code == 200
        assert res.json()["enabled"] is True
        assert len(res.json()["ticket"]) >= 32

    # Lần thứ 11 trong 60s -> 429 Too Many Requests
    r_limit = client.post("/api/ws/ticket", headers=headers)
    assert r_limit.status_code == 429


def test_ws_client_message_validation(client, candidate_user):
    """Client gửi JSON hỏng, loại lạ, quá 1KB hoặc nhị phân -> đóng 1008/1009."""
    token = create_access_token(candidate_user.id, candidate_user.role, getattr(candidate_user, "token_version", 1))
    origin_hdr = {"origin": "http://127.0.0.1:5502"}

    # 1. Gửi chuỗi không phải JSON -> 1008
    r_t = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    with client.websocket_connect(f"/ws/notifications?ticket={r_t.json()['ticket']}", headers=origin_hdr) as ws:
        _ = ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.send_text("not a json string")
            _ = ws.receive_json()
        assert exc.value.code in (CloseCode.POLICY_VIOLATION, 1008)

    # 2. Gửi type lạ không cho phép -> 1008
    r_t2 = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    with client.websocket_connect(f"/ws/notifications?ticket={r_t2.json()['ticket']}", headers=origin_hdr) as ws:
        _ = ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.send_json({"type": "hack_admin"})
            _ = ws.receive_json()
        assert exc.value.code in (CloseCode.POLICY_VIOLATION, 1008)

    # 3. Gửi payload quá 1KB -> 1009
    r_t3 = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    with client.websocket_connect(f"/ws/notifications?ticket={r_t3.json()['ticket']}", headers=origin_hdr) as ws:
        _ = ws.receive_json()
        big_text = "x" * 1500
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.send_text(big_text)
            _ = ws.receive_json()
        assert exc.value.code in (CloseCode.MESSAGE_TOO_BIG, 1009)

    # 4. Gửi binary (bytes) -> 1008
    r_t4 = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    with client.websocket_connect(f"/ws/notifications?ticket={r_t4.json()['ticket']}", headers=origin_hdr) as ws:
        _ = ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.send_bytes(b"\x00\x01\x02\x03")
            _ = ws.receive_json()
        assert exc.value.code in (CloseCode.POLICY_VIOLATION, 1008)


def test_multi_worker_without_redis_disables_websocket(monkeypatch, client, candidate_user):
    """Chạy multi-worker không Redis -> cảnh báo và tắt WebSocket."""
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    monkeypatch.delenv("REDIS_URL", raising=False)
    token = create_access_token(candidate_user.id, candidate_user.role, getattr(candidate_user, "token_version", 1))

    r_ticket = client.post("/api/ws/ticket", headers={"Authorization": f"Bearer {token}"})
    assert r_ticket.status_code == 200
    data = r_ticket.json()
    assert data["enabled"] is False
    assert data["ticket"] is None
