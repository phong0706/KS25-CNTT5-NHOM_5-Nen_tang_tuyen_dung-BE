"""Router API công khai Công ty (/api/companies*) & tương thích endpoint nội bộ."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.security import role_required, get_optional_user
from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.schemas.company import (
    CompanyOut,
    PublicCompanyDetailOut,
    PublicCompanyJobsOut,
    PublicCompanyListOut,
)
from app.schemas.job import FeaturedCompanyOut
from app.services.public_company_rules import check_company_search_rate_limit
from app.services.public_company_service import list_public_companies
from app.services.public_company_detail_service import (
    get_public_company_detail,
    list_public_company_jobs,
)

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/featured", response_model=list[FeaturedCompanyOut], summary="Công ty nổi bật theo số tin đang tuyển")
def list_featured_companies(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Company.id, Company.name, Company.slug, func.count(Job.id).label("job_count"))
        .join(Job, and_(Job.company_id == Company.id, Job.status == "published"))
        .where(Company.is_visible == True, Company.is_draft == False)  # noqa: E712
        .group_by(Company.id, Company.slug)
        .having(func.count(Job.id) > 0)
        .order_by(func.count(Job.id).desc(), Company.id.asc())
        .limit(limit)
    )
    return [FeaturedCompanyOut(id=r.id, name=r.name, slug=r.slug, job_count=int(r.job_count)) for r in db.execute(stmt).all()]


@router.get("", response_model=PublicCompanyListOut, summary="Danh sách công ty công khai")
def list_companies_public(
    request: Request,
    response: Response,
    q: str = Query("", max_length=120, description="Tìm kiếm theo tên, tagline, địa chỉ (bỏ dấu)"),
    industry: str = Query("", max_length=60),
    location: str = Query("", max_length=60),
    size: str = Query("", max_length=20),
    hiring: int = Query(1, ge=0, le=1),
    sort: str = Query("jobs", pattern="^(jobs|recent|name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=48),
    db: Session = Depends(get_db),
):
    if q.strip() and not check_company_search_rate_limit(request.client.host if request.client else ""):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn thao tác tìm kiếm quá nhanh. Vui lòng thử lại sau giây lát.",
        )
    response.headers["Cache-Control"] = "public, max-age=60"
    return list_public_companies(
        db,
        q=q,
        industry=industry,
        location=location,
        size=size,
        hiring=hiring,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/my-company", response_model=CompanyOut, summary="Lấy công ty của Nhà tuyển dụng hiện tại")
def get_my_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    company = db.scalar(select(Company).where(Company.employer_id == current_user.id))
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bạn chưa có thông tin công ty liên kết")
    return company


@router.get("/{slug}", response_model=PublicCompanyDetailOut, summary="Chi tiết công ty công khai theo slug")
def get_company_detail_public(slug: str, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=60"
    return get_public_company_detail(db, slug)


@router.get("/{slug}/jobs", response_model=PublicCompanyJobsOut, summary="Danh sách việc đang tuyển của công ty")
def get_company_jobs_public(
    slug: str,
    response: Response,
    sort: str = Query("latest", pattern="^(latest|salary)$"),
    location: str = Query("", max_length=60),
    level: str = Query("", max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=48),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    response.headers["Cache-Control"] = "public, max-age=60"
    return list_public_company_jobs(
        db,
        slug,
        sort=sort,
        location=location,
        level=level,
        page=page,
        page_size=page_size,
        current_user=current_user,
    )


@router.patch("/{company_id}/toggle-approval", response_model=CompanyOut, summary="Phê duyệt/Thu hồi công ty (chỉ Admin)")
def toggle_company_approval(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty")
    company.is_draft = not company.is_draft
    db.commit()
    db.refresh(company)
    return company
