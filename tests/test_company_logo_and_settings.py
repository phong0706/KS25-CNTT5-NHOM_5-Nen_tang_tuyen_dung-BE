"""Kiểm tra chức năng tải logo công ty, bảo mật IDOR và trạng thái hiển thị công khai."""
import io
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.user import User


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def setup_users_and_companies(db_session):
    u1 = User(email=f"emp_logo_1_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("Pass123"), role="employer", full_name="Emp 1")
    u2 = User(email=f"emp_logo_2_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("Pass123"), role="employer", full_name="Emp 2")
    db_session.add_all([u1, u2])
    db_session.commit()
    db_session.refresh(u1)
    db_session.refresh(u2)

    s1 = f"comp-1-logo-{uuid.uuid4().hex[:6]}"
    s2 = f"comp-2-logo-{uuid.uuid4().hex[:6]}"
    c1 = Company(employer_id=u1.id, name="Company 1 Logo Test", slug=s1, is_draft=False, status=CompanyStatus.PENDING)
    c2 = Company(employer_id=u2.id, name="Company 2 Logo Test", slug=s2, is_draft=False, status=CompanyStatus.PENDING)
    db_session.add_all([c1, c2])
    db_session.commit()
    db_session.refresh(c1)
    db_session.refresh(c2)

    t1 = create_access_token(u1.id, u1.role)
    t2 = create_access_token(u2.id, u2.role)
    return {"u1": u1, "u2": u2, "c1": c1, "c2": c2, "t1": t1, "t2": t2}


def _make_png_bytes(width=100, height=100):
    img = Image.new("RGB", (width, height), color=(15, 118, 110))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_valid_logo_sets_pending_review(setup_users_and_companies):
    client = TestClient(app)
    t1 = setup_users_and_companies["t1"]
    png_bytes = _make_png_bytes(200, 200)

    res = client.post(
        "/api/company/me/logo",
        headers={"Authorization": f"Bearer {t1}"},
        files={"file": ("logo.png", png_bytes, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["logo_status"] in ("pending", "pending_review")
    assert data["logo_url"] and data["logo_url"].startswith("/uploads/logos/")


def test_upload_logo_exceeds_size_returns_413(setup_users_and_companies):
    client = TestClient(app)
    t1 = setup_users_and_companies["t1"]
    big_bytes = b"0" * (205 * 1024)

    res = client.post(
        "/api/company/me/logo",
        headers={"Authorization": f"Bearer {t1}"},
        files={"file": ("big.png", big_bytes, "image/png")},
    )
    assert res.status_code == 413
    assert "200 KB" in res.json()["detail"]


def test_upload_logo_fake_exe_magic_bytes_returns_422(setup_users_and_companies):
    client = TestClient(app)
    t1 = setup_users_and_companies["t1"]
    fake_png = b"MZ\x90\x00\x03fake-executable-renamed-to-png"

    res = client.post(
        "/api/company/me/logo",
        headers={"Authorization": f"Bearer {t1}"},
        files={"file": ("malicious.png", fake_png, "image/png")},
    )
    assert res.status_code == 422
    assert "định dạng" in res.json()["detail"].lower()


def test_upload_logo_exceeds_dimension_returns_422(setup_users_and_companies):
    client = TestClient(app)
    t1 = setup_users_and_companies["t1"]
    huge_img = _make_png_bytes(600, 600)

    res = client.post(
        "/api/company/me/logo",
        headers={"Authorization": f"Bearer {t1}"},
        files={"file": ("huge.png", huge_img, "image/png")},
    )
    assert res.status_code == 422
    assert "512" in res.json()["detail"]


def test_remove_logo(setup_users_and_companies):
    client = TestClient(app)
    t1 = setup_users_and_companies["t1"]
    res = client.post(
        "/api/company/me/logo/remove",
        headers={"Authorization": f"Bearer {t1}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["logo_status"] == "removed"
    assert data["logo_url"] is None


def test_employer_cannot_modify_other_company_logo(setup_users_and_companies):
    client = TestClient(app)
    t1 = setup_users_and_companies["t1"]
    c2 = setup_users_and_companies["c2"]
    png_bytes = _make_png_bytes(100, 100)

    res = client.post(
        f"/api/company/{c2.id}/logo",
        headers={"Authorization": f"Bearer {t1}"},
        files={"file": ("logo.png", png_bytes, "image/png")},
    )
    assert res.status_code == 403
    assert "không có quyền" in res.json()["detail"]


def test_pending_logo_not_leaked_publicly(setup_users_and_companies, db_session):
    client = TestClient(app)
    c1 = setup_users_and_companies["c1"]
    c1.logo_url = "/uploads/logos/pending_secret.png"
    c1.logo_status = "pending_review"
    c1.is_visible = True
    c1.is_draft = False
    c1.status = CompanyStatus.VERIFIED
    c1.verification_status = "da_xac_minh"
    db_session.commit()

    res = client.get(f"/api/companies/{c1.slug}")
    assert res.status_code == 200
    detail = res.json()
    # logo_url must be None because logo_status is pending_review
    assert detail["logo_url"] is None
