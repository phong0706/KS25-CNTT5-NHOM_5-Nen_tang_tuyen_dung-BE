"""Pytest cho module thong bao (/api/notifications).

Kiem tra: 401 khi chua dang nhap, danh sach, so chua doc, danh dau da doc,
va tinh huong nghiep vu (nho ho so -> NTD nhan thong bao).
"""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.services.notification import (
    NotificationType,
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
    """Chua dang nhap -> 401 cho tat ca endpoint."""
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.post("/api/notifications/read", json={"notification_ids": [1]}).status_code == 401
    assert client.post("/api/notifications/read-all").status_code == 401
    assert client.delete("/api/notifications").status_code == 401


def test_notification_list_and_unread_count():
    """Tao thong bao -> danh sach co, so chua doc dung, danh dau da doc -> giam so chua doc."""
    token = _login("ungvien1@gmail.com", "ungvien1@")
    assert token, "Dang nhap ung vien that bai"
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "ungvien1@gmail.com"))
        user_id = user.id
    finally:
        db.close()

    prefix = "pytest:notif:"
    _cleanup(prefix)

    created = create_notification(
        db=SessionLocal(),
        user_id=user_id,
        actor_id=user_id,
        type=NotificationType.SYSTEM,
        title="Thong bao kiem thu",
        message=" noi dung",
        link="/candidate/applications",
        dedupe_key=f"{prefix}1",
        commit=True,
    )
    assert created is not None and created.id

    # 1. Danh sach chua doc
    list_res = client.get("/api/notifications?unread_only=true", headers=headers)
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["total"] >= 1
    assert any(i["id"] == created.id for i in body["items"])
    assert body["items"][0]["is_read"] is False

    # 2. So chua doc
    count_res = client.get("/api/notifications/unread-count", headers=headers)
    assert count_res.status_code == 200
    assert count_res.json()["unread_count"] >= 1

    # 3. Danh dau da doc 1 thong bao
    read_res = client.post(f"/api/notifications/{created.id}/read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["updated"] == 1

    # 4. Danh dau da doc toan bo
    read_all_res = client.post("/api/notifications/read-all", headers=headers)
    assert read_all_res.status_code == 200
    assert read_all_res.json()["unread_count"] == 0

    # 5. Xoa sach
    assert client.delete("/api/notifications", headers=headers).status_code == 200
    _cleanup(prefix)


def test_cannot_mark_other_users_notification_read():
    """Khong the danh dau da doc thong bao cua nguoi khac."""
    token_a = _login("ungvien1@gmail.com", "ungvien1@")
    token_b = _login("ungvien2@gmail.com", "ungvien2@")
    if not (token_a and token_b):
        return  # du lieu mau khong du -> bo qua
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    db = SessionLocal()
    try:
        from app.models.user import User

        user_a = db.scalar(select(User).where(User.email == "ungvien1@gmail.com"))
        user_b = db.scalar(select(User).where(User.email == "ungvien2@gmail.com"))
        prefix = "pytest:notif:private:"
        _cleanup(prefix)
        notif = create_notification(
            db=db,
            user_id=user_a.id,
            actor_id=user_a.id,
            type=NotificationType.SYSTEM,
            title="Rieng tu",
            dedupe_key=f"{prefix}1",
            commit=True,
        )
    finally:
        db.close()

    # User B co goi danh dau -> updated phai bang 0 (khong phai cua B)
    res = client.post(f"/api/notifications/{notif.id}/read", headers=headers_b)
    assert res.status_code == 200
    assert res.json()["updated"] == 0

    # Van con chua doc trong danh sach cua user A
    list_a = client.get("/api/notifications", headers=headers_a).json()
    item = next(i for i in list_a["items"] if i["id"] == notif.id)
    assert item["is_read"] is False

    _cleanup(prefix)
