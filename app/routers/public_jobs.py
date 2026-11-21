"""Router công khai cho Trang chủ & Trang tìm việc (< 80 dòng)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.job import FeaturedCompanyOut, HomeStatsOut, PublicJobsSearchOut
from app.services.public_jobs_detail import (
    get_featured_companies_data,
    get_home_stats_data,
    get_public_job_detail_data,
    toggle_saved_job_action,
)
from app.services.public_jobs_query import query_public_jobs

router = APIRouter(tags=["Public Jobs"])


@router.get("/jobs", response_model=PublicJobsSearchOut, summary="Tìm kiếm việc làm công khai kèm facets")
def search_public_jobs(
    q: str = Query("", max_length=120),
    location: str = Query("", max_length=200),
    level: str = Query("", max_length=200),
    type: str = Query("", max_length=200),
    category: str = Query("", max_length=200),
    company_id: int | None = Query(None, ge=1),
    company: str = Query("", max_length=120),
    salary_min: int | None = Query(None, ge=0),
    salary_max: int | None = Query(None, ge=0),
    skills: str = Query("", max_length=300),
    sort: str = Query("newest", description="newest|salary_desc|relevant"),
    distinct_company: bool = Query(False, description="Chỉ lấy 1 việc mới nhất cho mỗi công ty"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    return query_public_jobs(
        db, q=q, location=location, level=level, work_type=type, category=category,
        company_id=company_id, company=company, salary_min=salary_min, salary_max=salary_max,
        skills=skills, sort=sort, distinct_company=distinct_company, page=page,
        page_size=page_size, current_user=current_user,
    )


# Endpoint /companies/featured do router companies.py phụ trách để tránh trùng lặp route.


@router.get("/stats/home", response_model=HomeStatsOut, summary="Thống kê thật cho trang chủ")
def get_home_stats(db: Session = Depends(get_db)):
    return get_home_stats_data(db)


@router.post("/jobs/{job_id}/save", summary="Lưu hoặc bỏ lưu việc làm (cần đăng nhập)")
def toggle_save_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return toggle_saved_job_action(db, job_id, current_user)


@router.get("/jobs/{job_id}", summary="Chi tiết việc làm công khai")
def get_public_job_detail(job_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    return get_public_job_detail_data(db, job_id, user)
