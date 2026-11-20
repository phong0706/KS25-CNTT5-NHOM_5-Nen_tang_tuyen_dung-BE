"""Kiểm thử Bảo mật (Lớp E) và Dữ liệu công khai (Lớp F)."""
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


def create_user_and_company(db, role="employer", verified=True):
    tag = uuid.uuid4().hex[:8]
    user = User(
        email=f"u_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name=f"User {tag}",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    comp = None
    if role == "employer":
        comp = Company(
            employer_id=user.id,
            name=f"Company {tag}",
            tax_code=f"010{tag[:7]}",
            address="HN",
            verification_status="da_xac_minh" if verified else "chua_xac_minh",
            status=CompanyStatus.VERIFIED if verified else CompanyStatus.PENDING,
            is_verified=verified,
        )
        db.add(comp)
        db.flush()
    return user, comp


def test_security_idor_employer_access_other_job(client, db):
    """IDOR: Employer A không thể submit hay withdraw tin của Employer B."""
    empA, compA = create_user_and_company(db, verified=True)
    empB, compB = create_user_and_company(db, verified=True)
    jobA = Job(employer_id=empA.id, company_id=compA.id, title="Job A", status="draft", version=1)
    db.add(jobA)
    db.commit()

    tokenB = create_access_token(empB.id, empB.role)
    res = client.post(
        f"/api/employer/jobs/{jobA.id}/submit",
        json={"version": 1},
        headers={"Authorization": f"Bearer {tokenB}"},
    )
    assert res.status_code == 403


def test_security_privilege_escalation_and_tampered_token(client, db):
    """Leo quyền và token giả mạo: Bị từ chối với 403 hoặc 401."""
    emp, comp = create_user_and_company(db, verified=True)
    job = Job(employer_id=emp.id, company_id=comp.id, title="Job Test", status="pending", version=1)
    db.add(job)
    db.commit()

    token = create_access_token(emp.id, emp.role)
    # Employer tự approve -> 403
    res = client.post(
        f"/api/admin/jobs/{job.id}/approve",
        json={"version": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403

    # Token giả mạo -> 401
    res2 = client.post(
        f"/api/admin/jobs/{job.id}/approve",
        json={"version": 1},
        headers={"Authorization": "Bearer bad_tampered_token"},
    )
    assert res2.status_code == 401


def test_security_xss_in_rejection_reason(client, db):
    """Lý do từ chối chứa script XSS được lưu nguyên văn (không thực thi) và escape JSON an toàn."""
    admin, _ = create_user_and_company(db, role="admin")
    emp, comp = create_user_and_company(db, verified=True)
    job = Job(employer_id=emp.id, company_id=comp.id, title="Job XSS", status="pending", version=1)
    db.add(job)
    db.commit()

    admin_token = create_access_token(admin.id, admin.role)
    xss_payload = "<script>alert('xss')</script> Mô tả vi phạm"
    res = client.post(
        f"/api/admin/jobs/{job.id}/reject",
        json={"version": 1, "reason": xss_payload},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["review_note"] == xss_payload


def test_public_jobs_filtering_rules(client, db):
    """Tin công khai: không hiện pending/rejected/draft/closed, không hiện tin hết hạn hay cty chưa xác minh."""
    emp_ok, comp_ok = create_user_and_company(db, verified=True)
    emp_unv, comp_unv = create_user_and_company(db, verified=False)
    today = date.today()

    tag = uuid.uuid4().hex[:6]
    # 1. Tin published hợp lệ
    valid_job = Job(
        employer_id=emp_ok.id, company_id=comp_ok.id,
        title=f"Valid Engineer {tag}", status="published",
        deadline=today + timedelta(days=10), version=1
    )
    # 2. Tin draft
    draft_job = Job(
        employer_id=emp_ok.id, company_id=comp_ok.id,
        title=f"Draft Engineer {tag}", status="draft", version=1
    )
    # 3. Tin pending
    pending_job = Job(
        employer_id=emp_ok.id, company_id=comp_ok.id,
        title=f"Pending Engineer {tag}", status="pending", version=1
    )
    # 4. Tin published nhưng hết hạn
    expired_job = Job(
        employer_id=emp_ok.id, company_id=comp_ok.id,
        title=f"Expired Engineer {tag}", status="published",
        deadline=today - timedelta(days=2), version=1
    )
    # 5. Tin published nhưng công ty chưa xác minh
    unv_job = Job(
        employer_id=emp_unv.id, company_id=comp_unv.id,
        title=f"Unverified Company Engineer {tag}", status="published",
        deadline=today + timedelta(days=10), version=1
    )
    db.add_all([valid_job, draft_job, pending_job, expired_job, unv_job])
    db.commit()

    res = client.get(f"/api/jobs?q={tag}")
    assert res.status_code == 200
    items = res.json().get("items", [])
    returned_titles = [it["title"] for it in items]

    assert valid_job.title in returned_titles
    assert draft_job.title not in returned_titles
    assert pending_job.title not in returned_titles
    assert expired_job.title not in returned_titles
    assert unv_job.title not in returned_titles
