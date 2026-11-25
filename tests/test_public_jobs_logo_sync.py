import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db.session import SessionLocal
from app.models.company import Company, CompanyStatus
from app.models.job import Job

client = TestClient(app)

def test_public_jobs_search_returns_company_logo_for_active_companies():
    """
    Test ĐỎ: GET /api/jobs phải trả về company_logo và company_logo_2x
    khi công ty sở hữu việc làm có logo_status in ('active', 'approved') và có logo_url.
    """
    db = SessionLocal()
    try:
        # Xóa dữ liệu cũ nếu có
        db.execute(text("DELETE FROM jobs WHERE id = 99991"))
        db.execute(text("DELETE FROM companies WHERE id = 99991"))
        db.commit()

        # Tạo test company có logo active và 1 published job trên app_db_test bằng ORM
        comp = Company(
            id=99991,
            employer_id=1,
            name="Test Logo Company",
            slug="test-logo-company",
            logo_url="/uploads/logos/test_logo_256.webp",
            logo_url_2x="/uploads/logos/test_logo_512.webp",
            logo_status="active",
            verification_status="da_xac_minh",
            status=CompanyStatus.VERIFIED,
            is_verified=True,
            is_visible=True,
            is_draft=False,
        )
        db.add(comp)
        db.flush()

        job = Job(
            id=99991,
            employer_id=1,
            company_id=99991,
            title="Senior Cloud Engineer Test Logo",
            status="published",
            location="Hà Nội",
            work_type="Toàn thời gian",
            level="Senior",
            created_at=datetime.now(),
            published_at=datetime.now(),
        )
        db.add(job)
        db.commit()

        # Gọi API danh sách việc làm
        resp = client.get("/api/jobs?company=test-logo-company")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] >= 1, f"Kỳ vọng total >= 1 nhưng nhận {data['total']}"
        
        target = next((j for j in data["items"] if j["id"] == 99991), None)
        assert target is not None, "Không tìm thấy job 99991 trong kết quả"
        assert target["company_name"] == "Test Logo Company"
        assert target.get("company_logo") == "/uploads/logos/test_logo_256.webp", f"Lỗi: company_logo bị None hoặc sai: {target.get('company_logo')}"
        assert target.get("company_logo_2x") == "/uploads/logos/test_logo_512.webp", f"Lỗi: company_logo_2x bị None hoặc sai: {target.get('company_logo_2x')}"
    finally:
        db.execute(text("DELETE FROM jobs WHERE id = 99991"))
        db.execute(text("DELETE FROM companies WHERE id = 99991"))
        db.commit()
        db.close()
