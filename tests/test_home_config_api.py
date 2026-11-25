"""Integration & API Contract Tests cho Cấu hình trang chủ (Bước 5.B & 5.C).
Tuân thủ techrecruit-rules: < 195 dòng, chạy trên app_db_test qua conftest.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.user import User

client = TestClient(app)

# Helper tạo auth header từ user thật trong app_db_test
def get_auth_headers():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin", User.is_active == True).first()
        emp = db.query(User).filter(User.role == "employer", User.is_active == True).first()
        cand = db.query(User).filter(User.role == "candidate", User.is_active == True).first()
        return {
            "admin": {"Authorization": f"Bearer {create_access_token(user_id=admin.id, role='admin')}"},
            "employer": {"Authorization": f"Bearer {create_access_token(user_id=emp.id, role='employer')}"},
            "candidate": {"Authorization": f"Bearer {create_access_token(user_id=cand.id, role='candidate')}"},
        }
    finally:
        db.close()

HEADERS = get_auth_headers()


def test_public_home_salary_by_skill_endpoint():
    """Kiểm tra GET /api/home/salary-by-skill không cần đăng nhập, đúng cấu trúc."""
    res = client.get("/api/home/salary-by-skill")
    assert res.status_code == 200
    data = res.json()
    assert "computed_at" in data
    assert "min_sample" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    # Không để lộ email hay trường nhạy cảm
    assert "email" not in str(data)
    assert "updated_by" not in data


def test_public_home_featured_companies_endpoint():
    """Kiểm tra GET /api/home/featured-companies không cần auth, đúng schema."""
    res = client.get("/api/home/featured-companies")
    assert res.status_code == 200
    data = res.json()
    assert "computed_at" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        c = data["items"][0]
        assert "company_id" in c
        assert "name" in c
        assert "open_jobs" in c
        assert "logo_url" in c


def test_admin_salary_settings_auth_roles():
    """401 khi chưa đăng nhập, 403 khi là candidate/employer, 200 khi là admin."""
    # 401
    res_no_auth = client.get("/api/admin/home/salary-settings")
    assert res_no_auth.status_code == 401

    # 403 với employer
    res_emp = client.get("/api/admin/home/salary-settings", headers=HEADERS["employer"])
    assert res_emp.status_code == 403

    # 403 với candidate
    res_cand = client.get("/api/admin/home/salary-settings", headers=HEADERS["candidate"])
    assert res_cand.status_code == 403

    # 200 với admin
    res_adm = client.get("/api/admin/home/salary-settings", headers=HEADERS["admin"])
    assert res_adm.status_code == 200
    d = res_adm.json()
    assert "min_sample" in d
    assert "max_items" in d
    assert "version" in d
    assert "skills" in d


def test_admin_salary_settings_put_versioning_and_audit():
    """PUT /api/admin/home/salary-settings: kiểm tra version, tăng version và ghi audit."""
    get_res = client.get("/api/admin/home/salary-settings", headers=HEADERS["admin"])
    assert get_res.status_code == 200
    current_ver = get_res.json()["version"]

    # Gửi sai version -> 409 Conflict
    bad_ver_res = client.put(
        "/api/admin/home/salary-settings",
        json={"version": current_ver + 999, "min_sample": 5, "max_items": 6, "reason": "Lý do cập nhật hợp lệ 10kt"},
        headers=HEADERS["admin"],
    )
    assert bad_ver_res.status_code == 409
    assert "Cấu hình đã được người khác thay đổi" in bad_ver_res.json()["detail"]

    # Gửi hợp lệ -> 200, version tăng 1
    ok_res = client.put(
        "/api/admin/home/salary-settings",
        json={"version": current_ver, "min_sample": 6, "max_items": 7, "reason": "Cập nhật ngưỡng tin kiểm thử"},
        headers=HEADERS["admin"],
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["version"] == current_ver + 1
    assert ok_res.json()["min_sample"] == 6

    # Kiểm tra audit log có ghi nhận đúng section "salary"
    audit_res = client.get("/api/admin/home/audit?section=salary", headers=HEADERS["admin"])
    assert audit_res.status_code == 200
    logs = audit_res.json()["items"]
    assert len(logs) > 0
    assert logs[0]["reason"] == "Cập nhật ngưỡng tin kiểm thử"


def test_reject_direct_salary_injection_and_invalid_overrides():
    """Cấm gửi trực tiếp trường lương vào body (422) và ghim kỹ năng không tồn tại (422)."""
    # Gửi field lương trực tiếp -> 422 Unprocessable
    res_fake_sal = client.put(
        "/api/admin/home/salary-settings",
        json={"version": 1, "min_sample": 5, "max_items": 6, "salary": 99999999, "reason": "Thử ghi đè số lương"},
        headers=HEADERS["admin"],
    )
    assert res_fake_sal.status_code == 422

    # Ghim kỹ năng không tồn tại trong DB -> 422
    get_res = client.get("/api/admin/home/salary-settings", headers=HEADERS["admin"])
    curr_v = get_res.json()["version"]
    res_fake_skill = client.put(
        "/api/admin/home/skill-overrides",
        json={
            "version": curr_v,
            "overrides": [{"skill_id": 999999, "mode": "pinned", "position": 1}],
            "reason": "Thử ghim kỹ năng không tồn tại",
        },
        headers=HEADERS["admin"],
    )
    assert res_fake_skill.status_code == 422
