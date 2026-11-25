"""Kiểm thử tính nhất quán của trạng thái logo công ty và quy tắc ràng buộc thời gian duyệt hồ sơ.

Tuân thủ techrecruit-rules: <= 200 dòng, kiểm thử các góc khuất và parity giữa các endpoint.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.company_verification import CompanyVerification
from app.models.user import User
from app.services.company_logo_service import get_company_logo_state


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
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


def test_get_company_logo_state_all_cases():
    """Kiểm thử hàm get_company_logo_state làm nguồn chân lý duy nhất cho logo."""
    class DummyCompany:
        def __init__(self, logo_url, logo_status, logo_version=1):
            self.id = 999
            self.logo_url = logo_url
            self.logo_status = logo_status
            self.logo_version = logo_version

    # 1. Missing logo
    c_missing = DummyCompany(None, "missing")
    st = get_company_logo_state(None, c_missing)
    assert st["status"] == "missing"
    assert st["logo_url"] is None
    assert st["is_active"] is False

    # 2. Active logo với cache-busting version
    c_active = DummyCompany("/uploads/logos/rikkei.png", "active", logo_version=4)
    st = get_company_logo_state(None, c_active)
    assert st["status"] == "active"
    assert st["is_active"] is True
    assert st["logo_path"] == "/uploads/logos/rikkei.png?v=4"
    assert st["logo_url"] == "/uploads/logos/rikkei.png?v=4"

    # 3. Legacy 'approved' tự động chuẩn hóa thành 'active'
    c_legacy = DummyCompany("/uploads/logos/rikkei.png", "approved", logo_version=2)
    st = get_company_logo_state(None, c_legacy)
    assert st["status"] == "active"
    assert st["is_active"] is True
    assert st["logo_url"] == "/uploads/logos/rikkei.png?v=2"

    # 4. Pending logo
    c_pending = DummyCompany("/uploads/logos/temp.png", "pending")
    st = get_company_logo_state(None, c_pending)
    assert st["status"] == "pending"
    assert st["is_active"] is False

    # 5. Removed logo
    c_removed = DummyCompany("/uploads/logos/old.png", "removed")
    st = get_company_logo_state(None, c_removed)
    assert st["status"] == "removed"
    assert st["is_active"] is False
    assert st["logo_url"] is None


def test_company_7_logo_parity_across_endpoints(client, admin_token):
    """Kiểm thử tính nhất quán tuyệt đối giữa Admin Detail, Admin List và Public Detail cho Cty 7 (Rikkeisoft)."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Admin Detail
    r_detail = client.get("/api/admin/companies/7", headers=headers)
    assert r_detail.status_code == 200
    d_data = r_detail.json()
    assert d_data["id"] == 7
    assert d_data["logo_status"] == "active"
    assert d_data["logo_url"] is not None and "/uploads/logos/logo_7_" in d_data["logo_url"]
    assert "?v=" in d_data["logo_url"]

    # 2. Admin List
    r_list = client.get("/api/admin/companies?q=Rikkeisoft", headers=headers)
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    c7_item = next((it for it in items if it["id"] == 7), None)
    assert c7_item is not None
    assert c7_item["logo_status"] == "active"
    assert c7_item["logo_url"] is not None
    assert c7_item["logo_full_url"] is not None
    assert "?v=" in c7_item["logo_full_url"]
    # Parity tuyệt đối giữa Admin Detail và Admin List
    assert d_data["logo_path"] == c7_item["logo_url"]

    # 3. Public Detail
    r_pub = client.get("/api/companies/rikkeisoft")
    assert r_pub.status_code == 200
    p_data = r_pub.json()
    assert p_data["name"] == "Rikkeisoft"
    assert p_data["logo_url"] is not None and "/uploads/logos/logo_7_" in p_data["logo_url"]


def test_date_order_constraint_in_approve_and_reject(client, admin_token, db_session):
    """Kiểm thử backend chặn duyệt hoặc từ chối khi reviewed_at < submitted_at (HTTP 422 INVALID_DATE_ORDER)."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    emp = db_session.scalar(select(User).where(User.role == "employer").limit(1))

    # Tạo công ty test và hồ sơ có submitted_at trong tương lai (+1 ngày)
    comp = Company(name=f"Date Order Test {uuid.uuid4().hex[:6]}", slug=f"date-test-{uuid.uuid4().hex[:6]}", employer_id=emp.id, is_draft=False, verification_status="cho_duyet")
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    future_time = datetime.now() + timedelta(days=1)
    verif = CompanyVerification(
        company_id=comp.id, mst="0101248141", status="cho_duyet",
        license_storage_key="test_license_key.pdf", license_original_name="license.pdf",
        license_mime_type="application/pdf", license_size_bytes=1024,
        submitted_by=emp.id, version=1, submitted_at=future_time,
    )
    db_session.add(verif)
    db_session.commit()
    db_session.refresh(verif)

    try:
        # 1. Thử duyệt -> phải nhận 422 INVALID_DATE_ORDER
        r_app = client.post(f"/api/admin/company-verifications/{verif.id}/approve", headers=headers, json={"version": 1})
        assert r_app.status_code == 422
        assert r_app.json()["detail"]["code"] == "INVALID_DATE_ORDER"

        # 2. Thử từ chối -> phải nhận 422 INVALID_DATE_ORDER
        r_rej = client.post(f"/api/admin/company-verifications/{verif.id}/reject", headers=headers, json={"reason": "Lý do kiểm thử thứ tự thời gian hợp lệ"})
        assert r_rej.status_code == 422
        assert r_rej.json()["detail"]["code"] == "INVALID_DATE_ORDER"
    finally:
        db_session.delete(verif)
        db_session.delete(comp)
        db_session.commit()
