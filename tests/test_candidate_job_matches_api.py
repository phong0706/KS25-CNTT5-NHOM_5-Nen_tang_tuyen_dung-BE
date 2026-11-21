"""Integration & Security Tests cho Candidate Job Matches API (< 200 dòng)."""
from pathlib import Path
import sys
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.match_score import CandidateMatchingSetting
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
        u = User(email=f"admin_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("admin123"), role="admin", full_name="Admin Test")
        db_session.add(u)
        db_session.commit()
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))

@pytest.fixture(scope="module")
def employer_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "employer").limit(1))
    if not u:
        u = User(email=f"emp_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("emp123"), role="employer", full_name="Employer Test")
        db_session.add(u)
        db_session.commit()
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


@pytest.fixture(scope="module")
def candidate_user_and_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "candidate").limit(1))
    if not u:
        u = User(email=f"cand_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("cand123"), role="candidate", full_name="Candidate Test")
        db_session.add(u)
        db_session.commit()
    
    # Ensure profile has >= 3 skills
    prof = db_session.query(CandidateProfile).filter_by(user_id=u.id).first()
    if not prof:
        prof = CandidateProfile(user_id=u.id, skills_json='["Python", "FastAPI", "MySQL", "React"]', level="middle", location="Hà Nội")
        db_session.add(prof)
    else:
        prof.skills_json = '["Python", "FastAPI", "MySQL", "React"]'
    db_session.commit()

    token = create_access_token(u.id, u.role, getattr(u, "token_version", 1))
    return u, token


def test_unauthenticated_access_denied(client):
    res = client.get("/api/candidate/job-matches")
    assert res.status_code == 401
    res_set = client.get("/api/candidate/job-matches/settings")
    assert res_set.status_code == 401


def test_employer_and_admin_forbidden(client, admin_token, employer_token):
    # Employer MUST get 403 Forbidden
    res_emp = client.get("/api/candidate/job-matches", headers={"Authorization": f"Bearer {employer_token}"})
    assert res_emp.status_code == 403
    assert "Chức năng này chỉ dành cho: candidate" in res_emp.json()["detail"]

    # Admin MUST get 403 Forbidden
    res_admin = client.get("/api/candidate/job-matches", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 403


def test_pagination_validation(client, candidate_user_and_token):
    _, token = candidate_user_and_token
    headers = {"Authorization": f"Bearer {token}"}

    # page < 1 should return 422
    res_page_0 = client.get("/api/candidate/job-matches?page=0", headers=headers)
    assert res_page_0.status_code == 422

    # size < 1 should return 422
    res_size_0 = client.get("/api/candidate/job-matches?size=0", headers=headers)
    assert res_size_0.status_code == 422

    # size > 50 should return 422
    res_size_100 = client.get("/api/candidate/job-matches?size=100", headers=headers)
    assert res_size_100.status_code == 422


def test_candidate_matches_success_and_invariants(client, candidate_user_and_token):
    _, token = candidate_user_and_token
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/candidate/job-matches?page=1&size=10", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] in ("co_ket_qua", "rong", "can_them_ky_nang", "da_tat")
    assert "items" in data
    assert "total" in data
    assert data["formula_version"] == "v1.0"
    assert "data_as_of" in data

    if data["status"] == "co_ket_qua":
        assert len(data["items"]) > 0
        prev_score = 1.0
        for item in data["items"]:
            assert 0.0 <= item["total_score"] <= 1.0
            assert item["match_percentage"] == int(round(item["total_score"] * 100))
            assert item["total_score"] <= prev_score + 1e-4
            prev_score = item["total_score"]
            assert item["formula_version"] == "v1.0"
            assert "email" not in item
            assert "phone" not in item
            assert "company" in item
            assert "name" in item["company"]


def test_candidate_settings_workflow(client, candidate_user_and_token):
    user, token = candidate_user_and_token
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get settings
    res = client.get("/api/candidate/job-matches/settings", headers=headers)
    assert res.status_code == 200
    assert "is_enabled" in res.json()

    # 2. Turn OFF matching
    res_off = client.put("/api/candidate/job-matches/settings", json={"is_enabled": False}, headers=headers)
    assert res_off.status_code == 200
    assert res_off.json()["is_enabled"] is False

    # 3. Job matches should return status 'da_tat' and 0 items
    res_matches = client.get("/api/candidate/job-matches", headers=headers)
    assert res_matches.status_code == 200
    assert res_matches.json()["status"] == "da_tat"
    assert res_matches.json()["items"] == []

    # 4. Turn back ON matching
    res_on = client.put("/api/candidate/job-matches/settings", json={"is_enabled": True}, headers=headers)
    assert res_on.status_code == 200
    assert res_on.json()["is_enabled"] is True


def test_candidate_with_fewer_than_3_skills(client, db_session):
    u = db_session.scalar(select(User).where(User.email == "test_sparse_candidate@test.com"))
    if not u:
        u = User(email="test_sparse_candidate@test.com", password=hash_password("cand123"), role="candidate", full_name="Sparse Cand")
        db_session.add(u)
        db_session.commit()

    prof = db_session.query(CandidateProfile).filter_by(user_id=u.id).first()
    if not prof:
        prof = CandidateProfile(user_id=u.id, skills_json='["Python"]', level="junior")
        db_session.add(prof)
    else:
        prof.skills_json = '["Python"]'
    db_session.commit()

    token = create_access_token(u.id, u.role, getattr(u, "token_version", 1))
    res = client.get("/api/candidate/job-matches", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "can_them_ky_nang"
    assert res.json()["items"] == []


def test_applied_job_is_excluded(client, candidate_user_and_token, db_session):
    user, token = candidate_user_and_token
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/candidate/job-matches", headers=headers)
    if res.json()["status"] == "co_ket_qua" and res.json()["items"]:
        first_job_id = res.json()["items"][0]["job_id"]
        app_record = Application(candidate_id=user.id, job_id=first_job_id, status="SUBMITTED", cv_name_snapshot="cv.pdf")
        db_session.add(app_record)
        db_session.commit()
        try:
            res_after = client.get("/api/candidate/job-matches", headers=headers)
            ids = [it["job_id"] for it in res_after.json().get("items", [])]
            assert first_job_id not in ids
        finally:
            db_session.delete(app_record)
            db_session.commit()
