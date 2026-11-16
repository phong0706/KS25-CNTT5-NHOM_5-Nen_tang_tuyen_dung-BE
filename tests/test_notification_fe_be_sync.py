"""Pytest dong bo FE <-> BE cho module thong bao.

Kiem tra 3 phan:
    1. Link trong thong bao tro dung route FE that (frontend/pages/...).
    2. Response API co dung key ma FE doc (js/services/notificationApi.js).
    3. Cac endpoint doc dung theo format ma FE goi.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.services.notification import (
    notify_application_status_changed,
    notify_application_submitted,
    notify_job_status_changed,
)

client = TestClient(app)

# Cac route FE that (frontend/pages/...) — khop voi link BE tao ra.
FE_ROUTES = [
    "pages/employer/applications.html",
    "pages/candidate/applications.html",
    "pages/employer/jobs.html",
]


def _login(email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json().get("access_token")


def test_notification_links_point_to_real_fe_routes():
    """Link thong bao phai tro toi route FE that + co query param id de deep-link."""
    db = SessionLocal()
    try:
        users = db.scalars(select(User).limit(2)).all()
        assert len(users) >= 2, "Cần ít nhất 2 user trong DB"
        emp_id, cand_id = users[0].id, users[1].id

        n1 = notify_application_submitted(
            db, employer_id=emp_id, candidate_name="A", job_title="J",
            application_id=42, candidate_id=cand_id, commit=True,
        )
        n2 = notify_application_status_changed(
            db, candidate_id=cand_id, status="screening", status_label="Đang xem xét",
            job_title="J", application_id=42, actor_id=emp_id, commit=True,
        )
        n3 = notify_job_status_changed(
            db, employer_id=emp_id, job_id=7, job_title="Tin",
            status="published", status_label="Đang tuyển", actor_id=emp_id, commit=True,
        )
        assert n1 and n2 and n3, "Không tạo được thông báo để kiểm tra link"

        for link in (n1.link, n2.link, n3.link):
            assert link and link.startswith("/"), f"Link phải bắt đầu bằng '/': {link}"
            path = link.split("?")[0].lstrip("/")
            assert path in FE_ROUTES, f"Link trỏ sai route FE: {link}"

        # Query param id để FE mở thẳng đúng đối tượng
        assert "app_id=42" in n1.link
        assert "app_id=42" in n2.link
        assert "job_id=7" in n3.link

        for n in (n1, n2, n3):
            db.delete(n)
        db.commit()
    finally:
        db.close()


def test_response_shape_matches_fe_contract():
    """Response phải có đúng key mà FE đọc trong notificationApi.js."""
    token = _login("ungvien1@gmail.com", "ungvien1@")
    assert token, "Đăng nhập thất bại"
    headers = {"Authorization": f"Bearer {token}"}

    # unread-count -> FE đọc res.unread_count
    res = client.get("/api/notifications/unread-count", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "unread_count" in body and isinstance(body["unread_count"], int)

    # list -> FE đọc res.items / total / page / page_size / total_pages / unread_count
    res = client.get("/api/notifications?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    body = res.json()
    for key in ("items", "total", "page", "page_size", "total_pages", "unread_count"):
        assert key in body, f"Thiếu key '{key}' trong response list"

    # item -> FE đọc id, type, title, message, link, is_read, created_at, actor_name
    if body["items"]:
        item = body["items"][0]
        for key in ("id", "type", "title", "message", "link", "is_read", "created_at", "actor_name"):
            assert key in item, f"Thiếu key '{key}' trong item"


def test_read_endpoints_return_updated_and_unread_count():
    """FE đọc res.updated và res.unread_count sau khi đánh dấu đã đọc."""
    token = _login("ungvien1@gmail.com", "ungvien1@")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/notifications/read-all", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "updated" in body and "unread_count" in body

    # Id không tồn tại -> updated = 0 (không đánh dấu nhầm của người khác)
    res = client.post("/api/notifications/read", json={"notification_ids": [999999]}, headers=headers)
    assert res.status_code == 200
    assert res.json()["updated"] == 0
