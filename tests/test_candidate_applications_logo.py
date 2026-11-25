"""Unit and integration tests for company logo in candidate applications."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application
from app.models.company import Company
from app.models.job import Job
from app.models.user import User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def candidate_auth():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == "candidate").first()
        token = create_access_token(
            user_id=user.id,
            role=user.role,
            token_version=getattr(user, "token_version", 1),
        )
        return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user.id}
    finally:
        db.close()


def test_candidate_applications_list_includes_company_logo(client, candidate_auth):
    headers = candidate_auth["headers"]
    res = client.get("/api/candidate/applications", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0

    rikkei_app = next(
        (it for it in data["items"] if it.get("job", {}).get("company_slug") == "rikkeisoft"),
        None,
    )
    assert rikkei_app is not None, "Candidate should have an application for Rikkeisoft"
    job = rikkei_app["job"]
    assert job.get("company_logo") is not None
    assert "/uploads/logos/" in job["company_logo"]
    assert "?v=" in job["company_logo"]


def test_candidate_application_detail_includes_company_logo(client, candidate_auth):
    headers = candidate_auth["headers"]
    res = client.get("/api/candidate/applications", headers=headers)
    assert res.status_code == 200
    data = res.json()

    rikkei_app = next(
        (it for it in data["items"] if it.get("job", {}).get("company_slug") == "rikkeisoft"),
        None,
    )
    assert rikkei_app is not None

    app_id = rikkei_app["id"]
    res_detail = client.get(f"/api/candidate/applications/{app_id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    job = detail.get("job", {})
    assert job.get("company_logo") is not None
    assert "/uploads/logos/" in job["company_logo"]
    assert "?v=" in job["company_logo"]


def test_candidate_applications_fallback_when_no_logo(client, candidate_auth):
    headers = candidate_auth["headers"]
    res = client.get("/api/candidate/applications", headers=headers)
    assert res.status_code == 200
    data = res.json()

    no_logo_app = next(
        (it for it in data["items"] if it.get("job", {}).get("company_slug") != "rikkeisoft"),
        None,
    )
    if no_logo_app:
        job = no_logo_app["job"]
        # If company in DB has no logo, company_logo should be None
        db = SessionLocal()
        try:
            comp = db.query(Company).filter(Company.slug == job.get("company_slug")).first()
            if comp and not comp.logo_url:
                assert job.get("company_logo") is None
        finally:
            db.close()
