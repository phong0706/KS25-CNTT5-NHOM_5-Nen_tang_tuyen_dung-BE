"""test_search_suggest.py
Kiểm tra số đếm của gợi ý tìm kiếm khớp chính xác với total của /api/jobs?company=slug,
với cả tên có dấu và không dấu.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.session import SessionLocal
from app.models.company import Company
from app.models.job import Job
from app.routers.search_insights import get_search_suggestions
from app.services.public_jobs_query import count_public_jobs, query_public_jobs


def test_search_suggest_company_count_matches_jobs_api():
    db = SessionLocal()
    try:
        # Chuẩn bị dữ liệu mẫu cho test
        comp = db.query(Company).filter(Company.slug == "khoi-nghiep-test").first()
        if not comp:
            comp = Company(
                employer_id=1,
                name="Khởi nghiệp Sáng tạo Xanh",
                slug="khoi-nghiep-test",
                status="verified",
                verification_status="da_xac_minh",
                is_visible=True,
                is_verified=True,
            )
            db.add(comp)
            db.commit()
            db.refresh(comp)

        job = db.query(Job).filter(Job.company_id == comp.id).first()
        if not job:
            job = Job(
                employer_id=1,
                company_id=comp.id,
                title="Lập trình viên Khởi nghiệp",
                status="published",
            )
            db.add(job)
            db.commit()

        # 1. Test với từ khóa có dấu "Khởi"
        res_accent = get_search_suggestions(q="Khởi", db=db)
        items_accent = res_accent.get("items", [])
        comp_items_accent = [it for it in items_accent if it["type"] == "company" and it["slug"] == "khoi-nghiep-test"]
        assert len(comp_items_accent) > 0, "Phải tìm thấy công ty với từ khóa có dấu 'Khởi'"
        suggest_cnt_accent = comp_items_accent[0]["count"]

        # Gọi API query jobs theo company slug
        jobs_res = query_public_jobs(
            db, q="", location="", level="", work_type="", category="",
            company_id=None, company="khoi-nghiep-test", salary_min=None, salary_max=None,
            skills="", sort="newest", distinct_company=False, page=1, page_size=10, current_user=None
        )
        assert suggest_cnt_accent == jobs_res.total, f"Số đếm gợi ý ({suggest_cnt_accent}) phải bằng jobs total ({jobs_res.total})"

        # 2. Test với từ khóa không dấu "Khoi"
        res_no_accent = get_search_suggestions(q="Khoi", db=db)
        items_no_accent = res_no_accent.get("items", [])
        comp_items_no_accent = [it for it in items_no_accent if it["type"] == "company" and it["slug"] == "khoi-nghiep-test"]
        assert len(comp_items_no_accent) > 0, "Phải tìm thấy công ty với từ khóa không dấu 'Khoi'"
        suggest_cnt_no_accent = comp_items_no_accent[0]["count"]

        assert suggest_cnt_no_accent == jobs_res.total, f"Số đếm gợi ý không dấu ({suggest_cnt_no_accent}) phải bằng jobs total ({jobs_res.total})"
        assert suggest_cnt_accent == suggest_cnt_no_accent, "Số đếm có dấu và không dấu phải bằng nhau"
    finally:
        db.close()
