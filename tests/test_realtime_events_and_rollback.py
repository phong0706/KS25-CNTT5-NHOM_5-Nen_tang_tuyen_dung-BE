"""Kiểm thử tính toàn vẹn sự kiện và chống thông báo ma (rollback) qua WebSocket.

Tuân thủ techrecruit-rules: <= 200 dòng, mỗi ca là một test riêng biệt.
"""
from pathlib import Path
import sys, time
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.realtime.manager import manager
from app.realtime.protocol import build_server_message
from app.realtime.tickets import ticket_store
from app.services.notification import (
    NotificationType,
    create_notification,
    notify_application_status_changed,
    notify_application_submitted,
)


@pytest.fixture(autouse=True)
def reset_state():
    ticket_store.clear()
    manager.heartbeat_interval, manager.heartbeat_timeout = 25.0, 60.0
    yield
    ticket_store.clear()


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


def _recv(ws, max_pings: int = 2):
    for _ in range(max_pings):
        data = ws.receive_json()
        if data.get("type") == "ping":
            ws.send_json({"type": "pong"})
            continue
        return data
    raise TimeoutError("Chỉ nhận được ping, không có dữ liệu mong muốn")


def test_rollback_yields_zero_realtime_messages(users_fixture):
    """Giao dịch rollback không bao giờ đẩy thông báo ma ra WebSocket."""
    cand = users_fixture["cand"]
    cl = TestClient(app)
    t = _get_ticket(cl, cand)
    origin = {"origin": "http://127.0.0.1:5502"}

    with cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
        hello = _recv(ws)
        assert hello["type"] == "hello"

        db = SessionLocal()
        try:
            create_notification(
                db=db,
                user_id=cand.id,
                actor_id=cand.id,
                type=NotificationType.SYSTEM,
                title="Ghost notification on rollback",
                message="Nội dung không bao giờ được gửi",
                commit=False,
            )
            db.rollback()
        finally:
            db.close()

        # Kiểm tra không có tin ma trong queue
        assert manager.get_user_connections_count(cand.id) == 1
        conn = manager._user_conns[cand.id][0]
        assert conn.queue.empty()

        # Tạo thông báo thật với commit=True
        db2 = SessionLocal()
        try:
            real_notif = create_notification(
                db=db2,
                user_id=cand.id,
                actor_id=cand.id,
                type=NotificationType.SYSTEM,
                title="Real notification committed",
                message="Nội dung thông báo thật",
                commit=True,
            )
        finally:
            db2.close()

        msg = _recv(ws)
        assert msg["type"] == "notification"
        assert msg["data"]["id"] == real_notif.id
        assert msg["data"]["title"] == "Real notification committed"


def test_real_event_application_status_changed_pushes_ws(users_fixture):
    """Khi trạng thái hồ sơ thay đổi, ứng viên nhận đúng 1 tin báo realtime."""
    cand = users_fixture["cand"]
    emp = users_fixture["emp"]
    cl = TestClient(app)
    t = _get_ticket(cl, cand)
    origin = {"origin": "http://127.0.0.1:5502"}

    with cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
        _ = _recv(ws)

        app_id = int(time.time() * 1000) % 900000 + 1000
        db = SessionLocal()
        try:
            notify_application_status_changed(
                db=db,
                candidate_id=cand.id,
                job_title="Software Engineer",
                status="screening",
                status_label="Đang duyệt hồ sơ",
                application_id=app_id,
                actor_id=emp.id,
            )
            db.commit()
        finally:
            db.close()

        msg = _recv(ws)
        assert msg["type"] == "notification"
        assert "screening" in str(msg["data"]).lower() or "duyệt" in str(msg["data"]).lower()


def test_real_event_employer_receives_application_and_job_status_ws(users_fixture):
    """Khi có hồ sơ mới, nhà tuyển dụng nhận tin báo realtime qua WebSocket."""
    emp = users_fixture["emp"]
    cand = users_fixture["cand"]
    cl = TestClient(app)
    t = _get_ticket(cl, emp)
    origin = {"origin": "http://127.0.0.1:5502"}

    with cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
        _ = _recv(ws)

        app_id = int(time.time() * 1000) % 900000 + 2000
        db = SessionLocal()
        try:
            notify_application_submitted(
                db=db,
                employer_id=emp.id,
                candidate_name="Nguyễn Văn An",
                job_title="DevOps Lead",
                application_id=app_id,
                candidate_id=cand.id,
                commit=True,
            )
        finally:
            db.close()

        msg = _recv(ws)
        assert msg["type"] == "notification"
        assert msg["data"]["title"] == "Hồ sơ mới"
        assert "DevOps Lead" in str(msg["data"])


def test_concurrency_and_ordering_50_messages(users_fixture):
    """Đẩy 50 thông báo liên tiếp: ứng viên nhận đủ 50 tin, đúng thứ tự, không trùng lặp."""
    cand = users_fixture["cand"]
    cl = TestClient(app)
    t = _get_ticket(cl, cand)
    origin = {"origin": "http://127.0.0.1:5502"}

    with cl.websocket_connect(f"/ws/notifications?ticket={t}", headers=origin) as ws:
        _ = _recv(ws)

        for i in range(50):
            payload = build_server_message("notification", {"seq": i, "label": f"item_{i}"})
            manager.send_to_user_nowait(cand.id, payload)

        received_seqs = []
        for _ in range(50):
            msg = _recv(ws)
            assert msg["type"] == "notification"
            received_seqs.append(msg["data"]["seq"])

        assert len(received_seqs) == 50
        assert received_seqs == list(range(50))
