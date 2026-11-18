"""Tests Concurrency, Idempotence & Security (Bước 5.D & 5.E).
Tuân thủ techrecruit-rules: < 195 dòng, chạy trên app_db_test.
"""
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.user import User

client = TestClient(app)


def get_test_users():
    db = SessionLocal()
    try:
        admins = db.query(User).filter(User.role == "admin", User.is_active == True).limit(2).all()
        emp = db.query(User).filter(User.role == "employer", User.is_active == True).first()
        return admins, emp
    finally:
        db.close()


def test_concurrency_two_admins_same_version():
    """Hai admin cùng lưu 1 cấu hình với cùng 1 version: đúng 1 thành công, 1 nhận 409."""
    admins, _ = get_test_users()
    token1 = create_access_token(user_id=admins[0].id, role="admin")
    token2 = create_access_token(user_id=admins[1].id, role="admin")
    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}

    # Lấy version hiện tại
    v = client.get("/api/admin/home/salary-settings", headers=h1).json()["version"]

    def put_req(headers, new_min):
        return client.put(
            "/api/admin/home/salary-settings",
            json={"version": v, "min_sample": new_min, "max_items": 6, "reason": "Thử nghiệm đồng thời 2 admin"},
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(put_req, h1, 6)
        f2 = pool.submit(put_req, h2, 7)
        r1 = f1.result()
        r2 = f2.result()

    statuses = [r1.status_code, r2.status_code]
    assert 200 in statuses
    assert 409 in statuses


def test_locked_admin_rejected_immediately():
    """Quản trị viên bị khoá tài khoản (is_active=False) bị từ chối 403 ngay dù token còn hạn."""
    db = SessionLocal()
    try:
        # Tạo hoặc lấy user bị khóa
        locked = db.query(User).filter(User.is_active == False).first()
        if not locked:
            locked = User(email="locked_adm@test.com", password="hash", role="admin", full_name="Admin Bị Khóa", is_active=False)
            db.add(locked)
            db.commit()
            db.refresh(locked)
        token = create_access_token(user_id=locked.id, role="admin")
    finally:
        db.close()

    res = client.get("/api/admin/home/salary-settings", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "khoá" in res.json()["detail"].lower()


def test_reason_html_script_escaped_safely():
    """Reason chứa HTML hoặc script được lưu nguyên văn nhưng không thực thi khi render."""
    admins, _ = get_test_users()
    h = {"Authorization": f"Bearer {create_access_token(user_id=admins[0].id, role='admin')}"}
    v = client.get("/api/admin/home/salary-settings", headers=h).json()["version"]

    xss_reason = "<script>alert('xss')</script> cập nhật lý do bảo mật"
    res = client.put(
        "/api/admin/home/salary-settings",
        json={"version": v, "min_sample": 5, "max_items": 6, "reason": xss_reason},
        headers=h,
    )
    assert res.status_code == 200

    # Lấy audit log kiểm tra
    audit_res = client.get("/api/admin/home/audit?section=salary", headers=h)
    assert audit_res.status_code == 200
    latest = audit_res.json()["items"][0]
    assert latest["reason"] == xss_reason
    # Không để lộ mật khẩu, token trong audit
    assert "password" not in str(latest)
    assert "token" not in str(latest)


def test_sql_injection_and_invalid_param_types():
    """Thử SQL injection hoặc kiểu tham số sai: trả 422, tuyệt đối không lỗi 500."""
    admins, _ = get_test_users()
    h = {"Authorization": f"Bearer {create_access_token(user_id=admins[0].id, role='admin')}"}

    # Position âm
    res_neg = client.put(
        "/api/admin/home/skill-overrides",
        json={"version": 1, "overrides": [{"skill_id": 1, "mode": "pinned", "position": -5}], "reason": "Position âm"},
        headers=h,
    )
    assert res_neg.status_code == 422

    # SQL Injection trong skill_id
    res_sqli = client.put(
        "/api/admin/home/skill-overrides",
        json={"version": 1, "overrides": [{"skill_id": "1' OR '1'='1", "mode": "pinned", "position": 1}], "reason": "Thử SQL injection"},
        headers=h,
    )
    assert res_sqli.status_code == 422

    # SQL Injection trong section của audit
    res_audit_sqli = client.get("/api/admin/home/audit?section=' UNION SELECT 1,2,3--", headers=h)
    assert res_audit_sqli.status_code in (200, 422)  # Nếu coi là chuỗi thường thì 200 items=[], nếu validate thì 422, KHÔNG 500
    assert res_audit_sqli.status_code != 500
