"""test_logo_moderation.py - Kiểm thử luồng duyệt logo và tự động gán company_id (<= 180 dòng)."""
from io import BytesIO
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User


def _make_png_bytes(w=100, h=100):
    img = Image.new("RGB", (w, h), color=(15, 118, 110))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def logo_test_env():
    db = SessionLocal()
    # Tạo employer user và company
    emp = db.query(User).filter(User.email == "test_emp_logo@tuyendung.com").first()
    if not emp:
        emp = User(email="test_emp_logo@tuyendung.com", role="employer", full_name="Logo Employer", password="dummy")
        db.add(emp)
        db.flush()

    comp = db.query(Company).filter(Company.employer_id == emp.id).first()
    if not comp:
        comp = Company(name="Công ty Cổ phần Logo Mới", employer_id=emp.id, status=CompanyStatus.VERIFIED, verification_status="da_xac_minh")
        db.add(comp)
        db.flush()

    # Tạo admin user
    adm = db.query(User).filter(User.email == "test_adm_logo@tuyendung.com").first()
    if not adm:
        adm = User(email="test_adm_logo@tuyendung.com", role="admin", full_name="Logo Admin", password="dummy")
        db.add(adm)
        db.flush()

    db.commit()
    db.refresh(emp)
    db.refresh(comp)
    db.refresh(adm)

    emp_token = create_access_token(user_id=emp.id, role=emp.role)
    adm_token = create_access_token(user_id=adm.id, role=adm.role)

    yield {"emp": emp, "comp": comp, "adm": adm, "emp_token": emp_token, "adm_token": adm_token}
    db.close()


def test_employer_upload_logo_creates_admin_notification(logo_test_env):
    client = TestClient(app)
    emp_token = logo_test_env["emp_token"]
    comp = logo_test_env["comp"]
    adm = logo_test_env["adm"]
    db = SessionLocal()

    # Đếm thông báo admin trước khi upload
    before_notifs = db.query(Notification).filter(Notification.user_id == adm.id, Notification.type == "logo_pending").count()

    png = _make_png_bytes(120, 120)
    res = client.post(
        "/api/company/me/logo",
        headers={"Authorization": f"Bearer {emp_token}"},
        files={"file": ("company_logo.png", png, "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["logo_status"] == "pending"

    # Admin nhận được thông báo chuông (đóng session cũ để đọc snapshot mới)
    db.close()
    db = SessionLocal()
    after_notifs = db.query(Notification).filter(Notification.user_id == adm.id, Notification.type == "logo_pending").count()
    assert after_notifs > before_notifs
    latest = db.query(Notification).filter(Notification.user_id == adm.id, Notification.type == "logo_pending").order_by(Notification.id.desc()).first()
    assert comp.name in latest.message
    assert "chờ duyệt" in latest.message
    db.close()


def test_admin_list_and_approve_logo_idempotent(logo_test_env):
    client = TestClient(app)
    adm_token = logo_test_env["adm_token"]
    comp = logo_test_env["comp"]
    emp = logo_test_env["emp"]
    db = SessionLocal()

    # Danh sách logo chờ duyệt
    res = client.get("/api/admin/company-logos?status=pending", headers={"Authorization": f"Bearer {adm_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["counts"]["pending"] >= 1
    found = any(it["company_id"] == comp.id for it in data["items"])
    assert found is True

    # Admin duyệt logo
    before_emp_notifs = db.query(Notification).filter(Notification.user_id == emp.id, Notification.type == "logo_approved").count()
    app_res = client.post(f"/api/admin/company-logos/{comp.id}/approve", headers={"Authorization": f"Bearer {adm_token}"})
    assert app_res.status_code == 200
    assert app_res.json()["logo_status"] == "approved"

    # NTD nhận thông báo duyệt (mở session mới đọc snapshot mới)
    db.close()
    db = SessionLocal()
    after_emp_notifs = db.query(Notification).filter(Notification.user_id == emp.id, Notification.type == "logo_approved").count()
    assert after_emp_notifs == before_emp_notifs + 1

    # Gọi lại duyệt khi đã approved -> idempotent, không tạo thêm thông báo mới
    app_res2 = client.post(f"/api/admin/company-logos/{comp.id}/approve", headers={"Authorization": f"Bearer {adm_token}"})
    assert app_res2.status_code == 200
    db.close()
    db = SessionLocal()
    after_emp_notifs2 = db.query(Notification).filter(Notification.user_id == emp.id, Notification.type == "logo_approved").count()
    assert after_emp_notifs2 == after_emp_notifs
    db.close()


def test_admin_reject_logo_requires_reason(logo_test_env):
    client = TestClient(app)
    adm_token = logo_test_env["adm_token"]
    comp = logo_test_env["comp"]
    emp = logo_test_env["emp"]
    db = SessionLocal()

    # Từ chối không có lý do hoặc < 10 ký tự -> lỗi 422
    rej_err = client.post(f"/api/admin/company-logos/{comp.id}/reject", headers={"Authorization": f"Bearer {adm_token}"}, json={"reason": "ngắn"})
    assert rej_err.status_code == 422

    # Từ chối với lý do rõ ràng
    reason_txt = "Logo chứa hình ảnh mờ và vi phạm bản quyền thương hiệu khác."
    rej_ok = client.post(f"/api/admin/company-logos/{comp.id}/reject", headers={"Authorization": f"Bearer {adm_token}"}, json={"reason": reason_txt})
    assert rej_ok.status_code == 200
    assert rej_ok.json()["logo_status"] == "rejected"

    # NTD nhận được thông báo kèm lý do
    rej_notif = db.query(Notification).filter(Notification.user_id == emp.id, Notification.type == "logo_rejected").order_by(Notification.id.desc()).first()
    assert rej_notif is not None
    assert reason_txt in rej_notif.message
    db.close()


def test_employer_new_job_automatically_bound_to_company(logo_test_env):
    client = TestClient(app)
    emp_token = logo_test_env["emp_token"]
    comp = logo_test_env["comp"]

    payload = {
        "title": "Kỹ sư Cầu nối BrSE Tiếng Nhật N2",
        "level": "Middle",
        "work_type": "Toàn thời gian",
        "location": "Hà Nội",
        "quantity": 2,
        "skills": ["Java", "Japanese N2"],
        "status": "draft",
    }
    res = client.post("/api/employer/jobs", headers={"Authorization": f"Bearer {emp_token}"}, json=payload)
    assert res.status_code == 201
    job_id = res.json()["id"]

    db = SessionLocal()
    j = db.get(Job, job_id)
    assert j is not None
    assert j.company_id == comp.id
    db.close()
