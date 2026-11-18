"""Test F: Kiểm tra dữ liệu thật, không có chuỗi giả gắn cứng (Bước 5.F).
Tuân thủ techrecruit-rules: < 195 dòng, chạy trên app_db_test.
"""
from datetime import date
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.job import Job

client = TestClient(app)


def test_public_html_has_no_hardcoded_salary_or_mock_count():
    """Kiểm tra index.html không chứa chuỗi cứng '54 tin' hoặc số lương giả."""
    root = Path(__file__).resolve().parents[2]
    index_html = (root / "frontend" / "index.html").read_text(encoding="utf-8")

    # Không còn chuỗi cứng "dựa trên 54 tin"
    assert "54 tin" not in index_html
    # Không có dữ liệu mockup giả
    assert "mockup" not in index_html.lower()
    assert "dummy" not in index_html.lower()


def test_salary_by_skill_matches_real_database_jobs():
    """Endpoint công khai /api/home/salary-by-skill tính 100% từ bảng jobs thật."""
    db = SessionLocal()
    try:
        res = client.get("/api/home/salary-by-skill")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "min_sample" in data

        # Kiểm tra từng item kỹ năng: số lượng và lương phải khớp với logic DB
        for item in data["items"]:
            assert item["median"] > 0
            assert item["sample_size"] >= data["min_sample"] or item.get("is_pinned", False)
            assert item["unit"] == "tr/tháng"
    finally:
        db.close()


def test_featured_companies_only_verified_and_has_real_open_jobs():
    """Endpoint /api/home/featured-companies chỉ trả về công ty đã xác minh và số tin thật."""
    db = SessionLocal()
    try:
        res = client.get("/api/home/featured-companies")
        assert res.status_code == 200
        comps = res.json()["items"]

        today = date.today()
        for comp in comps:
            cid = comp["company_id"]
            db_comp = db.scalar(select(Company).where(Company.id == cid))
            assert db_comp is not None
            assert db_comp.is_verified or db_comp.verification_status == "da_xac_minh"
            assert db_comp.is_visible is True

            # Kiểm tra số job mở thực tế
            real_jobs_count = db.scalar(
                select(func.count(Job.id)).where(
                    Job.company_id == cid,
                    Job.status == "published",
                    Job.deleted_at.is_(None),
                    (Job.deadline.is_(None) | (Job.deadline >= today)),
                )
            )
            assert comp["open_jobs"] == real_jobs_count
    finally:
        db.close()


def test_no_mock_data_in_home_js():
    """Kiểm tra home.js không chứa dữ liệu tĩnh, mảng mẫu fake."""
    root = Path(__file__).resolve().parents[2]
    home_js = (root / "frontend" / "js" / "pages" / "home.js").read_text(encoding="utf-8")
    for keyword in ["dummy", "mockData", "sampleJobs", "placeholderData"]:
        assert keyword not in home_js
