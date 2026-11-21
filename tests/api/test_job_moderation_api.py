"""Hợp đồng API (Contract) cho luồng duyệt tin tuyển dụng (Lớp C)."""
from datetime import date, timedelta
from pathlib import Path
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.user import User


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def setup_users_and_job(db):
    tag = uuid.uuid4().hex[:8]
    emp = User(
        email=f"e_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name="Employer Test",
        role="employer",
        is_active=True,
    )
    admin = User(
        email=f"a_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name="Admin Test",
        role="admin",
        is_active=True,
    )
    cand = User(
        email=f"c_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name="Candidate Test",
        role="candidate",
        is_active=True,
    )
    db.add_all([emp, admin, cand])
    db.flush()

    comp = Company(
        employer_id=emp.id,
        name=f"Comp {tag}",
        tax_code=f"010{tag[:7]}",
        address="HN",
        verification_status="da_xac_minh",
        status=CompanyStatus.VERIFIED,
        is_verified=True,
    )
    db.add(comp)
    db.flush()

    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title="Software Engineer",
        status="draft",
        version=1,
        deadline=date.today() + timedelta(days=15),
    )
    db.add(job)
    db.commit()
    return emp, admin, cand, comp, job


def test_api_submit_job_flow(client, db):
    emp, admin, cand, comp, job = setup_users_and_job(db)
    emp_token = create_access_token(emp.id, emp.role)
    admin_token = create_access_token(admin.id, admin.role)
    cand_token = create_access_token(cand.id, cand.role)

    # 401 Chưa đăng nhập
    res = client.post(f"/api/employer/jobs/{job.id}/submit", json={"version": 1})
    assert res.status_code == 401

    # 403 Sai vai trò (ứng viên gọi)
    res = client.post(
        f"/api/employer/jobs/{job.id}/submit",
        json={"version": 1},
        headers={"Authorization": f"Bearer {cand_token}"},
    )
    assert res.status_code == 403

    # 404 Không tồn tại
    res = client.post(
        "/api/employer/jobs/9999999/submit",
        json={"version": 1},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert res.status_code == 404

    # 409 VERSION_CONFLICT
    res = client.post(
        f"/api/employer/jobs/{job.id}/submit",
        json={"version": 99},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert res.status_code == 409
    assert res.json().get("detail") == "VERSION_CONFLICT"

    # 200 Thành công gửi duyệt (draft -> pending)
    res = client.post(
        f"/api/employer/jobs/{job.id}/submit",
        json={"version": 1},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"
    assert data["version"] == 2

    # 409 INVALID_TRANSITION (gửi lại lần nữa khi đang pending)
    res = client.post(
        f"/api/employer/jobs/{job.id}/submit",
        json={"version": 2},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert res.status_code == 409
    assert res.json().get("detail") == "INVALID_TRANSITION"


def test_api_admin_approve_and_reject_flow(client, db):
    emp, admin, cand, comp, job = setup_users_and_job(db)
    emp_token = create_access_token(emp.id, emp.role)
    admin_token = create_access_token(admin.id, admin.role)

    # Employer submit -> pending
    client.post(
        f"/api/employer/jobs/{job.id}/submit",
        json={"version": 1},
        headers={"Authorization": f"Bearer {emp_token}"},
    )

    # 403: Employer không thể gọi admin endpoint
    res = client.post(
        f"/api/admin/jobs/{job.id}/approve",
        json={"version": 2},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert res.status_code == 403

    # 422: Admin reject thiếu reason hoặc reason < 10 ký tự
    res = client.post(
        f"/api/admin/jobs/{job.id}/reject",
        json={"version": 2, "reason": "Ngắn"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 422

    # 200: Admin duyệt thành công
    res = client.post(
        f"/api/admin/jobs/{job.id}/approve",
        json={"version": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "published"
    assert data["version"] == 3

    # Kiểm tra an toàn: Response không lộ mật khẩu hay token
    body_str = res.text
    assert "password" not in body_str
    assert "token" not in body_str
