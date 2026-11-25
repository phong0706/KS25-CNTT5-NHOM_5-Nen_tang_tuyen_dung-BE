"""Unit, Integration & API Contract Tests cho Đồng bộ Logo công ty (<= 200 dòng)."""
from pathlib import Path
import sys, uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.user import User
from app.services.company_logo_service import (
    approve_company_logo, generate_logo_filename, get_home_companies,
    reject_company_logo, remove_company_logo, upload_company_logo, validate_logo_file,
)
from fastapi import HTTPException

import io
from PIL import Image, ImageDraw

def _make_test_image(fmt="PNG", w=120, h=120):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([w // 4, h // 4, 3 * w // 4, 3 * h // 4], fill=(255, 0, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()

PNG_BYTES = _make_test_image("PNG")
WEBP_BYTES = _make_test_image("WEBP")


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
    if not u:
        u = User(email=f"adm_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("admin123"), role="admin", full_name="Admin Test")
        db_session.add(u); db_session.commit()
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))

@pytest.fixture(scope="module")
def candidate_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "candidate").limit(1))
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


def test_validate_logo_file_security():
    # Hợp lệ
    assert validate_logo_file(PNG_BYTES, "test.png") == ".png"
    assert validate_logo_file(WEBP_BYTES, "test.webp") == ".webp"
    # File rỗng / đuôi sai / vượt dung lượng
    with pytest.raises(HTTPException) as exc: validate_logo_file(b"", "test.png")
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc: validate_logo_file(PNG_BYTES, "test.jpg")
    assert exc.value.status_code == 422
    # Chặn SVG, HTML, Script
    with pytest.raises(HTTPException) as exc: validate_logo_file(b"<svg>evil</svg>", "test.png")
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc: validate_logo_file(b"<html><script>alert(1)</script></html>", "test.webp")
    assert exc.value.status_code == 422


def test_generate_logo_filename_safe():
    fn = generate_logo_filename(7, 3, ".png")
    assert fn.startswith("logo_7_v3_")
    assert ".." not in fn and "/" not in fn and "\\" not in fn


def test_upload_and_approve_lifecycle(db_session, client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # 1. Upload logo mới cho công ty 7
    res_up = client.post("/api/companies/7/logos", files={"file": ("logo.png", PNG_BYTES, "image/png")}, headers=headers)
    assert res_up.status_code == 200
    logo_data = res_up.json()
    logo_id = logo_data["id"]
    assert logo_data["status"] == "cho_duyet"
    assert logo_data["is_current"] is False

    # 2. Duyệt logo -> transaction thành công
    res_app = client.post(f"/api/company-logos/{logo_id}/approve", headers=headers)
    assert res_app.status_code == 200
    app_data = res_app.json()
    assert app_data["status"] == "dang_dung"
    assert app_data["is_current"] is True

    # Kiểm tra database: công ty 7 phải cập nhật logo_version và logo_url
    db_session.rollback()
    c7 = db_session.get(Company, 7)
    assert c7.logo_url.startswith("/uploads/logos/")
    assert c7.logo_status in ("approved", "active")

    # Duyệt lại lần 2 (idempotent): thành công, không lỗi
    res_app2 = client.post(f"/api/company-logos/{logo_id}/approve", headers=headers)
    assert res_app2.status_code == 200


def test_reject_validation_and_flow(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Upload logo mới
    res_up = client.post("/api/companies/7/logos", files={"file": ("test_rej.png", PNG_BYTES, "image/png")}, headers=headers)
    l_id = res_up.json()["id"]

    # Từ chối lý do ngắn (< 10 ký tự) -> 422
    res_rej_short = client.post(f"/api/company-logos/{l_id}/reject", json={"reason": "Xấu quá"}, headers=headers)
    assert res_rej_short.status_code == 422

    # Từ chối hợp lệ
    res_rej = client.post(f"/api/company-logos/{l_id}/reject", json={"reason": "Ảnh bị mờ và không đúng nhận diện thương hiệu"}, headers=headers)
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "tu_choi"


def test_conflict_409_when_newer_pending(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Upload logo v1
    res1 = client.post("/api/companies/7/logos", files={"file": ("v1.png", PNG_BYTES, "image/png")}, headers=headers)
    id1 = res1.json()["id"]
    # Upload logo v2 (mới hơn đang chờ)
    res2 = client.post("/api/companies/7/logos", files={"file": ("v2.png", PNG_BYTES, "image/png")}, headers=headers)
    id2 = res2.json()["id"]

    # Cố duyệt bản cũ id1 khi có id2 mới hơn -> phải trả 409 Conflict
    res_app_old = client.post(f"/api/company-logos/{id1}/approve", headers=headers)
    assert res_app_old.status_code == 409
    assert "Có bản logo mới hơn" in res_app_old.json()["detail"]

    # Duyệt bản mới id2 -> thành công
    res_app_new = client.post(f"/api/company-logos/{id2}/approve", headers=headers)
    assert res_app_new.status_code == 200


def test_remove_logo(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res_del = client.delete("/api/companies/7/logo", headers=headers)
    assert res_del.status_code == 200
    db_session.rollback()
    c7 = db_session.get(Company, 7)
    assert c7.logo_url is None
    assert c7.logo_status == "missing"

    # Home companies endpoint không trả logo cho công ty 7 nữa
    res_home = client.get("/api/home/companies")
    assert res_home.status_code == 200
    c7_home = next((c for c in res_home.json() if c["id"] == 7), None)
    if c7_home:
        assert c7_home["logo_url"] is None

    # Khôi phục lại logo ban đầu cho công ty 7
    db_session.rollback()
    db_session.query(CompanyLogo).filter(CompanyLogo.company_id == 7).update({"is_current": False, "status": "da_thay"})
    l1 = db_session.get(CompanyLogo, 1)
    if l1:
        l1.is_current = True
        l1.status = "dang_dung"
    c7 = db_session.get(Company, 7)
    if c7:
        c7.logo_url = "/uploads/logos/logo_7_6bb6f6bf6f3b.png"
        c7.logo_status = "active"
        c7.logo_version = 1
    db_session.commit()


def test_home_companies_contract(client, candidate_token):
    # Public endpoint không cần token
    res = client.get("/api/home/companies")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    for comp in data:
        assert "id" in comp and "name" in comp and "open_jobs" in comp and "logo_version" in comp
        assert "email" not in comp and "phone" not in comp and "tax_code" not in comp
        if comp["logo_url"]:
            assert f"?v={comp['logo_version']}" in comp["logo_url"]

    # Phân quyền: candidate không được duyệt logo -> 403
    res_forbid = client.post("/api/company-logos/1/approve", headers={"Authorization": f"Bearer {candidate_token}"})
    assert res_forbid.status_code == 403
