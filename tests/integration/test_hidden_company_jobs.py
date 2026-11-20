"""test_hidden_company_jobs.py
Integration tests xác nhận:
- Tin của công ty ẩn (is_visible=0) KHÔNG xuất hiện ở bất kỳ endpoint công khai nào.
- Endpoint chi tiết /api/jobs/{id}: khách xem không thấy link trang công ty ẩn (company_slug=None).
- Chủ sở hữu / Admin vẫn xem được tin và link quản trị.
"""
import uuid
from datetime import date, timedelta
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.user import User


def test_hidden_company_jobs_not_in_public_endpoints():
    client = TestClient(app)
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    emp = User(
        email=f"emp_{tag}@test.vn",
        full_name=f"Emp {tag}",
        password=hash_password("Pass123!"),
        role="employer",
        is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    # Tạo công ty ẩn: is_visible = False
    comp = Company(
        employer_id=emp.id,
        owner_id=emp.id,
        name=f"Công ty Ẩn Test {tag}",
        slug=f"cong-ty-an-test-{tag}",
        status=CompanyStatus.PENDING,
        verification_status="chua_xac_minh",
        is_visible=False,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    # Tạo tin tuyển dụng cho công ty ẩn
    job = Job(
        company_id=comp.id,
        employer_id=emp.id,
        title=f"Lập trình viên Ẩn {tag}",
        status="published",
        deadline=date.today() + timedelta(days=30),
        skills=["Python", "FastAPI"],
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        # 1. GET /api/jobs -> Không được chứa job.id
        res_jobs = client.get("/api/jobs")
        assert res_jobs.status_code == 200
        job_ids = [j["id"] for j in res_jobs.json().get("items", [])]
        assert job.id not in job_ids, f"Tin của công ty ẩn ID={job.id} xuất hiện trong /api/jobs!"

        # 2. GET /api/jobs?company_id={comp.id} -> 0 kết quả
        res_by_comp = client.get(f"/api/jobs?company_id={comp.id}")
        assert res_by_comp.status_code == 200
        assert res_by_comp.json().get("total", 0) == 0

        # 3. Khách gọi GET /api/jobs/{job.id} -> company_slug phải là None
        res_detail_guest = client.get(f"/api/jobs/{job.id}")
        assert res_detail_guest.status_code == 200
        assert res_detail_guest.json().get("company_slug") is None, "Khách không được thấy link company_slug của công ty ẩn"

        # 4. Chủ sở hữu gọi GET /api/jobs/{job.id} -> company_slug tồn tại
        h_emp = {"Authorization": f"Bearer {create_access_token(emp.id, emp.role)}"}
        res_detail_owner = client.get(f"/api/jobs/{job.id}", headers=h_emp)
        assert res_detail_owner.status_code == 200
        assert res_detail_owner.json().get("company_slug") == comp.slug

    finally:
        db.query(Job).filter_by(id=job.id).delete()
        db.query(Company).filter_by(id=comp.id).delete()
        db.query(User).filter_by(id=emp.id).delete()
        db.commit()
        db.close()
