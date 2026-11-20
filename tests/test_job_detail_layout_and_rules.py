"""test_job_detail_layout_and_rules.py - Kiểm thử đơn vị, tích hợp và hợp đồng trang chi tiết việc làm.

Tuân thủ techrecruit-rules: <= 200 dòng, mỗi ca kiểm thử một khía cạnh riêng biệt.
"""
from pathlib import Path
import sys
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token
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
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


@pytest.fixture(scope="module")
def candidate_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "candidate").limit(1))
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


# ============================================================================
# A. ĐƠN VỊ (UNIT LOGIC FORMAT & FILTERS)
# ============================================================================

def _py_format_salary(job: dict) -> str:
    """Tái hiện hàm formatSalary chuẩn frontend (hỗ trợ đảo ngược min > max)."""
    if not job or job.get("is_salary_negotiable"):
        return "Thỏa thuận"
    min_v, max_v = job.get("salary_min"), job.get("salary_max")
    if not min_v and not max_v:
        return "Thỏa thuận"

    def to_tr(v):
        if not v or v <= 0: return ""
        return f"{round(v / 1e6, 1):g} Tr" if v >= 1e6 else f"{int(v):,} ₫"

    if min_v and max_v:
        if min_v > max_v:
            min_v, max_v = max_v, min_v
        return f"{to_tr(min_v)} - {to_tr(max_v)}"
    return f"Từ {to_tr(min_v)}" if min_v else f"Đến {to_tr(max_v)}"


def _filter_related_jobs(current_job_id: int, jobs: list[dict]) -> list[dict]:
    """Lọc tối đa 4 việc liên quan, loại bỏ tin test/rác và chính việc đang xem."""
    result = []
    for j in jobs:
        if j.get("id") == current_job_id:
            continue
        title = (j.get("title") or "").lower()
        if "mmmmmm" in title or title.startswith("test ") or title == "test":
            continue
        result.append(j)
        if len(result) == 4:
            break
    return result


def test_unit_salary_formatting_cases():
    """Định dạng lương: có min-max, chỉ min, chỉ max, thỏa thuận, khoảng đảo ngược."""
    assert _py_format_salary({"salary_min": 15000000, "salary_max": 25000000}) == "15 Tr - 25 Tr"
    assert _py_format_salary({"salary_min": 30000000, "salary_max": 10000000}) == "10 Tr - 30 Tr"
    assert _py_format_salary({"salary_min": 20000000, "salary_max": None}) == "Từ 20 Tr"
    assert _py_format_salary({"salary_min": None, "salary_max": 40000000}) == "Đến 40 Tr"
    assert _py_format_salary({"is_salary_negotiable": True}) == "Thỏa thuận"
    assert _py_format_salary({"salary_min": None, "salary_max": None}) == "Thỏa thuận"


def test_unit_filter_related_jobs_excludes_self_and_tests():
    """Lọc việc liên quan loại bỏ chính nó, loại bỏ tin test và giới hạn tối đa 4 thẻ."""
    sample_jobs = [
        {"id": 1, "title": "Senior Frontend Dev"},
        {"id": 2, "title": "Backend Python"},
        {"id": 3, "title": "mmmmmm"},  # test rác
        {"id": 4, "title": "test job 123"},  # test
        {"id": 5, "title": "Mobile Engineer"},
        {"id": 6, "title": "DevOps Engineer"},
        {"id": 7, "title": "Security Analyst"},
    ]
    filtered = _filter_related_jobs(1, sample_jobs)
    assert len(filtered) == 4
    assert [j["id"] for j in filtered] == [2, 5, 6, 7]
    assert all(j["id"] != 1 for j in filtered)


# ============================================================================
# B. TÍCH HỢP (DATABASE & INTEGRATION)
# ============================================================================

def test_integration_job_detail_returns_accurate_data_and_company_info(client, db_session):
    """Trang chi tiết trả đúng dữ liệu tin tuyển dụng và trường công ty."""
    res = client.get("/api/jobs/1")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["title"] is not None
    assert "salary_min" in data and "salary_max" in data
    assert "company_name" in data
    assert "company_is_verified" in data
    assert data["company_is_verified"] is True  # Job 1 thuộc công ty đã xác minh


def test_integration_unverified_company_jobs_do_not_have_verified_flag(client):
    """Tin thuộc công ty chưa xác minh (như #130) trả company_is_verified = False."""
    res = client.get("/api/jobs/130")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 130
    assert data["company_is_verified"] is False


def test_integration_related_jobs_only_returns_published(client):
    """Việc liên quan chỉ lấy từ các tin có trạng thái published."""
    res = client.get("/api/jobs?page_size=20")
    assert res.status_code == 200
    items = res.json()["items"]
    # Tất cả items công khai phải có status published (hoặc không chứa draft)
    assert all(it.get("status") in (None, "published") for it in items)


# ============================================================================
# C. HỢP ĐỒNG API (API CONTRACT & STATUS CODES)
# ============================================================================

def test_contract_job_detail_success_200(client):
    """Chi tiết tin công khai trả 200."""
    res = client.get("/api/jobs/71")
    assert res.status_code == 200
    assert res.json()["id"] == 71


def test_contract_job_detail_not_found_404(client):
    """ID không tồn tại trả 404."""
    res = client.get("/api/jobs/9999999")
    assert res.status_code == 404
    assert "Không tìm thấy" in res.json()["detail"]


def test_contract_draft_job_hidden_from_public_and_candidate_404(client, candidate_token, admin_token):
    """Tin chưa công khai (draft) trả 404 với khách và ứng viên, 200 với admin."""
    # Job 16 là tin draft
    assert client.get("/api/jobs/16").status_code == 404
    assert client.get("/api/jobs/16", headers={"Authorization": f"Bearer {candidate_token}"}).status_code == 404
    res_admin = client.get("/api/jobs/16", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
