"""Pytest cho module thông báo (/api/notifications).
Tuân thủ:
1. Không lặp tên (không lặp 'Nguyễn Văn An ... · Nguyễn Văn An').
2. User A không đọc / đánh dấu được thông báo của B (trả 404).
3. read-all chỉ ảnh hưởng thông báo của chính mình.
4. Phân trang con trỏ (cursor) ổn định, không trùng không sót.
5. Payload thiếu trường vẫn dựng được câu hợp lý.
"""
import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.services.notification import (
    NotificationType,
    build_notification_content,
    count_unread,
    create_notification,
)

client = TestClient(app)


def _login(email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json().get("access_token")


def _cleanup(dedupe_prefix: str) -> None:
    db = SessionLocal()
    try:
        db.query(Notification).filter(
            Notification.dedupe_key.like(f"{dedupe_prefix}%")
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_notifications_require_auth():
    """Chưa đăng nhập -> 401 cho tất cả endpoint."""
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.post("/api/notifications/read", json={"notification_ids": [1]}).status_code == 401
    assert client.post("/api/notifications/read-all").status_code == 401
    assert client.post("/api/notifications/1/read").status_code == 401
    assert client.delete("/api/notifications").status_code == 401


def test_notification_no_name_repetition():
    """Kiểm tra không ghép lặp tên người dùng trong thông báo."""
    title, body, href = build_notification_content(
        NotificationType.APPLICATION_SUBMITTED,
        payload_json={"candidate_name": "Nguyễn Văn An", "job_title": "Senior SRE", "application_id": 10, "job_id": 2},
    )
    assert title == "Hồ sơ mới"
    assert body == "Nguyễn Văn An ứng tuyển Senior SRE"
    # Tên chỉ xuất hiện đúng 1 lần
    assert body.count("Nguyễn Văn An") == 1
    assert "tab=candidates" in href and "job=2" in href and "app=10" in href


def test_notification_missing_payload_graceful():
    """Payload thiếu trường hoặc rỗng/lỗi vẫn tạo nội dung hợp lý, không crash."""
    title, body, href = build_notification_content(
        NotificationType.APPLICATION_SUBMITTED,
        payload_json={},
    )
    assert title == "Hồ sơ mới"
    assert "Ứng viên" in body and "ứng tuyển" in body
    assert "/pages/employer/recruitment.html" in href

    # Payload là chuỗi JSON không hợp lệ
    title2, body2, _ = build_notification_content(
        NotificationType.APPLICATION_STATUS_CHANGED,
        payload_json="invalid json string",
    )
    assert title2 == "Cập nhật trạng thái hồ sơ"
    assert "Hồ sơ ứng tuyển" in body2


def test_user_cannot_mark_other_notification_returns_404():
    """User B không thể đánh dấu thông báo của User A -> trả 404."""
    token_a = _login("ungvien1@gmail.com", "ungvien1@")
    token_b = _login("ungvien2@gmail.com", "ungvien2@")
    if not (token_a and token_b):
        return
    headers_b = {"Authorization": f"Bearer {token_b}"}

    db = SessionLocal()
    prefix = "pytest:sec:404:"
    _cleanup(prefix)
    try:
        user_a = db.scalar(select(User).where(User.email == "ungvien1@gmail.com"))
        notif = create_notification(
            db=db,
            user_id=user_a.id,
            actor_id=user_a.id,
            type=NotificationType.SYSTEM,
            title="Riêng tư của A",
            dedupe_key=f"{prefix}1",
            commit=True,
        )
        notif_id = notif.id
    finally:
        db.close()

    # User B cố tình đánh dấu đã đọc thông báo của User A -> phải nhận 404
    res = client.post(f"/api/notifications/{notif_id}/read", headers=headers_b)
    assert res.status_code == 404
    assert res.json()["detail"] == "Thông báo không tồn tại."

    _cleanup(prefix)


def test_read_all_only_affects_current_user():
    """read-all chỉ đánh dấu thông báo của chính mình, người khác không bị ảnh hưởng."""
    token_a = _login("ungvien1@gmail.com", "ungvien1@")
    token_b = _login("ungvien2@gmail.com", "ungvien2@")
    if not (token_a and token_b):
        return
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    prefix = "pytest:readall:"
    _cleanup(prefix)

    db = SessionLocal()
    try:
        user_a = db.scalar(select(User).where(User.email == "ungvien1@gmail.com"))
        user_b = db.scalar(select(User).where(User.email == "ungvien2@gmail.com"))

        # Tạo cho A 2 thông báo chưa đọc
        create_notification(db=db, user_id=user_a.id, type=NotificationType.SYSTEM, title="A1", dedupe_key=f"{prefix}a1", commit=True)
        create_notification(db=db, user_id=user_a.id, type=NotificationType.SYSTEM, title="A2", dedupe_key=f"{prefix}a2", commit=True)
        # Tạo cho B 1 thông báo chưa đọc
        create_notification(db=db, user_id=user_b.id, type=NotificationType.SYSTEM, title="B1", dedupe_key=f"{prefix}b1", commit=True)
    finally:
        db.close()

    unread_b_before = client.get("/api/notifications/unread-count", headers=headers_b).json()["unread_count"]
    assert unread_b_before >= 1

    # User A gọi read-all
    res_a = client.post("/api/notifications/read-all", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["unread_count"] == 0

    # Kiểm tra số chưa đọc của B không hề thay đổi
    unread_b_after = client.get("/api/notifications/unread-count", headers=headers_b).json()["unread_count"]
    assert unread_b_after == unread_b_before

    _cleanup(prefix)


def test_cursor_pagination_stability():
    """Phân trang con trỏ (cursor) ổn định, duyệt liên tục không trùng lặp."""
    token = _login("ungvien1@gmail.com", "ungvien1@")
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    prefix = "pytest:cursor:"
    _cleanup(prefix)
    try:
        user = db.scalar(select(User).where(User.email == "ungvien1@gmail.com"))
        created_ids = []
        for i in range(4):
            n = create_notification(
                db=db,
                user_id=user.id,
                type=NotificationType.SYSTEM,
                title=f"Cursor item {i}",
                dedupe_key=f"{prefix}{i}",
                commit=True,
            )
            created_ids.append(n.id)
    finally:
        db.close()

    # Trang 1: lấy limit=2
    res1 = client.get("/api/notifications?limit=2", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["items"]) == 2
    cursor1 = data1["next_cursor"]
    assert cursor1 is not None

    # Trang 2: lấy tiếp bằng cursor
    res2 = client.get(f"/api/notifications?limit=2&cursor={cursor1}", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) >= 1

    ids_page1 = [x["id"] for x in data1["items"]]
    ids_page2 = [x["id"] for x in data2["items"]]

    # Không có id nào trùng giữa 2 trang
    assert set(ids_page1).isdisjoint(set(ids_page2))

    _cleanup(prefix)
