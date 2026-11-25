"""Integration tests: Ma trận phân quyền xem hồ sơ ứng viên (SEC-01).
Tuân thủ techrecruit-rules: < 200 dòng, dọn dẹp dữ liệu, test độc lập.
"""
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, ApplicationStatus
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.user import User

client = TestClient(app)

@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def _user(db, role, name, phone="0912345678"):
    u = User(email=f"{name}_{uuid.uuid4().hex[:6]}@t.vn", password=hash_password("pw123"), role=role, full_name=f"U_{name}", phone=phone, is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u, create_access_token(u.id, u.role, getattr(u, "token_version", 1))

def _setup_context(db, is_public=True):
    cand_u, cand_t = _user(db, "candidate", "cand", phone="0988776655")
    prof = CandidateProfile(user_id=cand_u.id, public_id=f"pub_{uuid.uuid4().hex[:18]}", is_public=is_public, headline="Dev", location="Hà Nội")
    db.add(prof); db.commit(); db.refresh(prof)
    emp_a, emp_a_t = _user(db, "employer", "empa")
    comp_a = Company(name="CompA", slug=f"ca-{uuid.uuid4().hex[:6]}", employer_id=emp_a.id)
    db.add(comp_a); db.commit(); db.refresh(comp_a)
    job_a = Job(title="Job A", company_id=comp_a.id, employer_id=emp_a.id, status="published")
    db.add(job_a); db.commit(); db.refresh(job_a)
    emp_b, emp_b_t = _user(db, "employer", "empb")
    app_a = Application(candidate_id=cand_u.id, job_id=job_a.id, status=ApplicationStatus.SUBMITTED.value)
    db.add(app_a); db.commit(); db.refresh(app_a)
    return prof, cand_u, emp_a_t, emp_b_t, app_a, job_a

def test_employer_a_with_active_application_gets_full_access(db):
    prof, cand_u, emp_a_t, _, _, _ = _setup_context(db, is_public=True)
    res = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_a_t}"})
    assert res.status_code == 200
    data = res.json()
    assert data["access"] == "full"
    assert data["phone"] == "0988776655"
    assert data["email"] == cand_u.email
    assert "birthday" not in data and "address" not in data
    assert "user_id" not in data and "id" not in data
    assert len(data.get("applications_to_you", [])) >= 1

def test_employer_b_without_application_gets_public_access(db):
    prof, cand_u, _, emp_b_t, _, _ = _setup_context(db, is_public=True)
    res = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_b_t}"})
    assert res.status_code == 200
    data = res.json()
    assert data["access"] == "public"
    assert "phone" not in data
    assert "email" not in data
    assert "applications_to_you" not in data
    assert "birthday" not in data and "address" not in data
    assert data["full_name"] == cand_u.full_name
    assert data["city"] == "Hà Nội"

def test_candidate_turns_off_public_employer_a_still_full_employer_b_404(db):
    prof, _, emp_a_t, emp_b_t, _, _ = _setup_context(db, is_public=False)
    # Employer A đã có đơn -> vẫn xem full
    res_a = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_a_t}"})
    assert res_a.status_code == 200
    assert res_a.json()["access"] == "full"
    # Employer B chưa có đơn -> 404, body GIỐNG HỆT khi public_id sai
    res_b = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_b_t}"})
    assert res_b.status_code == 404
    res_fake = client.get(f"/api/employer/candidates/non_existent_key_12345", headers={"Authorization": f"Bearer {emp_b_t}"})
    assert res_b.json() == res_fake.json()

def test_candidate_withdrawn_application_access_downgrade(db):
    prof, _, emp_a_t, _, app_a, _ = _setup_context(db, is_public=True)
    # Ứng viên rút đơn
    app_a.status = ApplicationStatus.WITHDRAWN.value
    from datetime import datetime, timezone
    app_a.withdrawn_at = datetime.now(timezone.utc)
    db.commit()
    # Employer A bị hạ cấp xuống 'public'
    res = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_a_t}"})
    assert res.status_code == 200
    data = res.json()
    assert data["access"] == "public"
    assert "phone" not in data and "email" not in data
    # Nếu tắt công khai sau khi rút đơn -> thành 404
    prof.is_public = False
    db.commit()
    res2 = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_a_t}"})
    assert res2.status_code == 404

def test_admin_views_private_profile_full_access_logged(db):
    prof, cand_u, _, _, _, _ = _setup_context(db, is_public=False)
    admin_u, admin_t = _user(db, "admin", "admn")
    res = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {admin_t}"})
    assert res.status_code == 200
    data = res.json()
    assert data["access"] == "full"
    assert data["phone"] == "0988776655"
    assert data["email"] == cand_u.email

def test_candidate_c_cannot_view_other_candidate_profile_403(db):
    prof, _, _, _, _, _ = _setup_context(db, is_public=True)
    other_c, other_t = _user(db, "candidate", "otherc")
    res = client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {other_t}"})
    assert res.status_code == 403
    assert "không có quyền" in res.json().get("detail", "")
