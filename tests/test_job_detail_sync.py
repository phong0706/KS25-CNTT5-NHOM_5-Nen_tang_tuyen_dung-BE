"""test_job_detail_sync.py - Kiểm thử tích hợp & hợp đồng API trang chi tiết việc làm (< 200 dòng)."""
from pathlib import Path
import sys, uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.job import Job
from app.models.user import User


@pytest.fixture(scope="module")
def client(): return TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@pytest.fixture(scope="module")
def admin_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "admin").limit(1))
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))

@pytest.fixture(scope="module")
def candidate_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "candidate").limit(1))
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


def test_job_detail_api_contract_success(client):
    # Job 71 là tin Remote Senior Python FastAPI Engineer (Rikkeisoft - ID 7)
    res = client.get("/api/jobs/71")
    assert res.status_code == 200
    data = res.json()

    # Kiểm tra các trường cần thiết
    assert data["id"] == 71
    assert "FastAPI" in data["title"]
    assert data["company_id"] == 7
    assert data["company_slug"] == "rikkeisoft"
    assert data["company_name"] == "Rikkeisoft"
    assert data["company_logo"] is not None
    assert "/uploads/logos/" in data["company_logo"]

    # Bảo mật: Không được lộ email hoặc thông tin nhạy cảm của nhà tuyển dụng
    assert "employer_email" not in data
    assert "email" not in data
    assert "password" not in data
    assert "hashed_password" not in data


def test_job_detail_not_found_returns_404(client):
    res = client.get("/api/jobs/9999999")
    assert res.status_code == 404
    assert "Không tìm thấy" in res.json()["detail"]


def test_job_detail_draft_hidden_from_public_and_candidate(client, candidate_token, admin_token):
    # Job 16 là tin draft (Security Engineer - AppSec & Pentest)
    # Khách vãng lai -> 404
    res_anon = client.get("/api/jobs/16")
    assert res_anon.status_code == 404

    # Ứng viên -> 404
    res_cand = client.get("/api/jobs/16", headers={"Authorization": f"Bearer {candidate_token}"})
    assert res_cand.status_code == 404

    # Admin / Chủ sở hữu -> 200 xem trước được
    res_admin = client.get("/api/jobs/16", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert res_admin.json()["id"] == 16


def test_related_jobs_and_search_excludes_test_jobs(client):
    # API tìm kiếm và việc liên quan không được trả về tin có tên test ("mmmmmm" - ID 97)
    res = client.get("/api/jobs?page_size=24")
    assert res.status_code == 200
    items = res.json()["items"]
    ids = [item["id"] for item in items]
    titles = [item["title"].lower() for item in items]

    assert 97 not in ids, "Tin test ID 97 ('mmmmmm') không được xuất hiện trong danh sách việc làm!"
    assert not any("mmmmmm" in t for t in titles)
    assert not any(t.startswith("test ") or t == "test" for t in titles)
