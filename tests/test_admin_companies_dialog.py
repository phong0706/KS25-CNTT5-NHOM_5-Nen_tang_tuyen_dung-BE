"""Integration & API Contract Tests cho Hộp thoại Quản lý Công ty (Admin)."""
from pathlib import Path
import sys
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, and_, func

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.job import Job
from app.models.user import User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def admin_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "admin").limit(1))
    if not u:
        u = User(email=f"admin_{uuid.uuid4().hex[:6]}@test.com", password_hash=hash_password("admin123"), role="admin", full_name="Admin Test")
        db_session.add(u)
        db_session.commit()
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


@pytest.fixture(scope="module")
def employer_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "employer").limit(1))
    if not u:
        u = User(email=f"emp_{uuid.uuid4().hex[:6]}@test.com", password_hash=hash_password("emp123"), role="employer", full_name="Employer Test")
        db_session.add(u)
        db_session.commit()
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


@pytest.fixture(scope="module")
def candidate_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "candidate").limit(1))
    if not u:
        u = User(email=f"cand_{uuid.uuid4().hex[:6]}@test.com", password_hash=hash_password("cand123"), role="candidate", full_name="Candidate Test")
        db_session.add(u)
        db_session.commit()
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


def test_admin_company_detail_contract(client, admin_token, employer_token, candidate_token):
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    headers_emp = {"Authorization": f"Bearer {employer_token}"}
    headers_cand = {"Authorization": f"Bearer {candidate_token}"}

    # 1. 200 OK cho admin
    res = client.get("/api/admin/companies/7", headers=headers_admin)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == 7
    assert data["name"] == "Rikkeisoft"
    assert "open_jobs_count" in data
    assert "verification_status" in data
    assert "verification" in data

    # 2. 403 Forbidden cho employer và candidate
    res_emp = client.get("/api/admin/companies/7", headers=headers_emp)
    assert res_emp.status_code == 403

    res_cand = client.get("/api/admin/companies/7", headers=headers_cand)
    assert res_cand.status_code == 403

    # 3. 401 Unauthorized khi chưa đăng nhập
    res_unauth = client.get("/api/admin/companies/7")
    assert res_unauth.status_code == 401

    # 4. 404 Not Found khi công ty không tồn tại
    res_404 = client.get("/api/admin/companies/999999", headers=headers_admin)
    assert res_404.status_code == 404


def test_open_jobs_count_consistency(client, admin_token, db_session):
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/companies/7", headers=headers_admin)
    assert res.status_code == 200
    modal_count = res.json()["open_jobs_count"]

    # Đếm trực tiếp trong DB với điều kiện published
    db_count = db_session.scalar(
        select(func.count(Job.id)).where(and_(Job.company_id == 7, Job.status == "published"))
    ) or 0
    assert modal_count == db_count


def test_delete_company_requires_exact_name(client, admin_token, db_session):
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    emp = db_session.scalar(select(User).where(User.role == "employer").limit(1))
    # Tạo công ty tạm để test xóa
    temp_comp = Company(name=f"Công ty Tạm {uuid.uuid4().hex[:6]}", slug=f"co-tam-{uuid.uuid4().hex[:6]}", employer_id=emp.id, is_draft=False)
    db_session.add(temp_comp)
    db_session.commit()
    db_session.refresh(temp_comp)
    cid = temp_comp.id
    target_name = temp_comp.name

    # 1. Xóa không có tên -> 422
    r_empty = client.delete(f"/api/admin/companies/{cid}", headers=headers_admin)
    assert r_empty.status_code == 422

    # 2. Xóa sai tên (thường hóa, thừa khoảng trắng) -> 422
    r_wrong = client.request("DELETE", f"/api/admin/companies/{cid}", headers=headers_admin, json={"confirm_name": target_name.lower()})
    assert r_wrong.status_code == 422

    r_space = client.request("DELETE", f"/api/admin/companies/{cid}", headers=headers_admin, json={"confirm_name": f" {target_name} "})
    assert r_space.status_code == 422

    # Kiểm tra công ty vẫn còn trong DB
    assert db_session.get(Company, cid) is not None

    # 3. Xóa đúng tên chính xác -> 200 và công ty bị xóa
    r_ok = client.request("DELETE", f"/api/admin/companies/{cid}", headers=headers_admin, json={"confirm_name": target_name})
    assert r_ok.status_code == 200
    db_session.rollback()
    assert db_session.get(Company, cid) is None


def test_approve_and_revoke_flow_parity(client, admin_token, db_session):
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    emp = db_session.scalar(select(User).where(User.role == "employer").limit(1))

    # Tạo công ty có hồ sơ chờ duyệt
    from app.models.company_verification import CompanyVerification
    comp = Company(name=f"Cty Kiểm Thử Duyệt {uuid.uuid4().hex[:6]}", slug=f"cty-duyet-{uuid.uuid4().hex[:6]}", employer_id=emp.id, is_draft=False, verification_status="cho_duyet")
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    verif = CompanyVerification(
        company_id=comp.id, mst="0101248141", status="cho_duyet",
        license_storage_key="test_license_key.pdf", license_original_name="license.pdf",
        license_mime_type="application/pdf", license_size_bytes=1024,
        submitted_by=emp.id, version=1
    )
    db_session.add(verif)
    db_session.commit()
    db_session.refresh(verif)

    # 1. Duyệt xác minh
    r_app = client.post(f"/api/admin/company-verifications/{verif.id}/approve", headers=headers_admin, json={"version": 1})
    assert r_app.status_code == 200

    # Kiểm tra modal chi tiết
    r_detail = client.get(f"/api/admin/companies/{comp.id}", headers=headers_admin)
    assert r_detail.status_code == 200
    assert r_detail.json()["verification_status"] == "da_xac_minh"

    # 2. Thu hồi xác minh
    r_rev = client.post(f"/api/admin/companies/{comp.id}/revoke-verification", headers=headers_admin, json={"reason": "Thu hồi để kiểm tra tính năng parity giữa modal và list."})
    assert r_rev.status_code == 200

    r_detail_after = client.get(f"/api/admin/companies/{comp.id}", headers=headers_admin)
    assert r_detail_after.status_code == 200
    assert r_detail_after.json()["verification_status"] == "thu_hoi"

    # Dọn dẹp công ty test
    db_session.delete(verif)
    db_session.delete(comp)
    db_session.commit()

