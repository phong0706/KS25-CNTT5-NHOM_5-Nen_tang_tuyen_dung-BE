"""Router quản lý công ty / doanh nghiệp."""
import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_optional_user, role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job, MetaCategory, SavedJob
from app.models.user import User
from app.schemas.company import CompanyDetailOut, CompanyListOut, CompanyOut
from app.schemas.job import FeaturedCompanyOut, PublicJobCardOut

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/featured", response_model=list[FeaturedCompanyOut], summary="Công ty nổi bật theo số tin đang tuyển")
def list_featured_companies(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Company.id, Company.name, Company.slug, func.count(Job.id).label("job_count"))
        .join(Job, and_(Job.company_id == Company.id, Job.status == "published"))
        .where(Company.is_draft == False)  # noqa: E712
        .group_by(Company.id, Company.slug)
        .having(func.count(Job.id) > 0)
        .order_by(func.count(Job.id).desc(), Company.id.asc())
        .limit(limit)
    )
    return [FeaturedCompanyOut(id=r.id, name=r.name, slug=r.slug, job_count=int(r.job_count)) for r in db.execute(stmt).all()]


@router.get("", response_model=CompanyListOut, summary="Danh sách công ty kèm lọc, tìm kiếm, phân trang")
def list_companies(
    q: str = Query("", description="Tìm theo tên công ty hoặc địa chỉ"),
    industry_id: int | None = Query(None, description="Lọc theo ngành nghề"),
    sort: str = Query("jobs_desc", description="jobs_desc|name_asc|newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    job_sub = (
        select(Job.company_id, func.count(Job.id).label("cnt"))
        .where(Job.status == "published")
        .group_by(Job.company_id)
        .subquery()
    )

    stmt = (
        select(
            Company,
            MetaCategory.name.label("industry_name"),
            func.coalesce(job_sub.c.cnt, 0).label("job_count"),
        )
        .outerjoin(MetaCategory, Company.industry_id == MetaCategory.id)
        .outerjoin(job_sub, Company.id == job_sub.c.company_id)
    )

    if not current_user or current_user.role != "admin":
        stmt = stmt.where(Company.is_draft == False)  # noqa: E712

    kw = q.strip()
    if kw:
        stmt = stmt.where(or_(Company.name.ilike(f"%{kw}%"), Company.address.ilike(f"%{kw}%")))

    if industry_id:
        stmt = stmt.where(Company.industry_id == industry_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if sort == "name_asc":
        stmt = stmt.order_by(Company.name.asc())
    elif sort == "newest":
        stmt = stmt.order_by(Company.id.desc())
    else:
        stmt = stmt.order_by(func.coalesce(job_sub.c.cnt, 0).desc(), Company.name.asc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    rows = db.execute(stmt).all()

    items = [
        CompanyOut(
            id=r[0].id, name=r[0].name, slug=r[0].slug, employer_id=r[0].employer_id, is_draft=r[0].is_draft,
            logo_url=r[0].logo_url, cover_url=r[0].cover_url, description=r[0].description,
            industry_id=r[0].industry_id, industry_name=r[1], size=r[0].size, website=r[0].website,
            address=r[0].address, job_count=int(r[2] or 0), created_at=r[0].created_at,
        )
        for r in rows
    ]

    total_pages = max(1, math.ceil(total / page_size))
    return CompanyListOut(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/my-company", response_model=CompanyOut, summary="Lấy công ty của Nhà tuyển dụng hiện tại")
def get_my_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    company = db.scalar(select(Company).where(Company.employer_id == current_user.id))
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bạn chưa có thông tin công ty liên kết",
        )
    return company


@router.get("/{slug}", response_model=CompanyDetailOut, summary="Chi tiết công ty theo slug")
def get_company_detail_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    stmt = (
        select(Company, MetaCategory.name.label("industry_name"))
        .outerjoin(MetaCategory, Company.industry_id == MetaCategory.id)
        .where(Company.slug == slug)
    )
    if not current_user or current_user.role != "admin":
        stmt = stmt.where(Company.is_draft == False)  # noqa: E712

    row = db.execute(stmt).first()
    if not row and slug.isdigit():
        stmt = (
            select(Company, MetaCategory.name.label("industry_name"))
            .outerjoin(MetaCategory, Company.industry_id == MetaCategory.id)
            .where(Company.id == int(slug))
        )
        if not current_user or current_user.role != "admin":
            stmt = stmt.where(Company.is_draft == False)  # noqa: E712
        row = db.execute(stmt).first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty")

    company: Company = row[0]
    industry_name: str | None = row[1]

    jobs_stmt = (
        select(Job)
        .where(Job.company_id == company.id, Job.status == "published")
        .order_by(func.coalesce(Job.published_at, Job.created_at).desc())
    )
    jobs_rows = db.scalars(jobs_stmt).all()

    saved_ids = set()
    if current_user and jobs_rows:
        jids = [j.id for j in jobs_rows]
        saved_ids = set(
            db.scalars(
                select(SavedJob.job_id).where(SavedJob.user_id == current_user.id, SavedJob.job_id.in_(jids))
            ).all()
        )

    job_cards = [
        PublicJobCardOut(
            id=j.id, title=(j.title or "").replace("[Seed]", "").strip(), company_id=company.id,
            company_name=company.name, location=j.location, level=j.level, work_type=j.work_type,
            salary_min=j.salary_min, salary_max=j.salary_max, is_salary_negotiable=bool(j.is_salary_negotiable),
            skills=j.skills if isinstance(j.skills, list) else [], published_at=j.published_at,
            created_at=j.created_at, is_saved=j.id in saved_ids, is_expired=False, deadline=j.deadline,
        )
        for j in jobs_rows
    ]

    return CompanyDetailOut(
        id=company.id, name=company.name, slug=company.slug, employer_id=company.employer_id,
        is_draft=company.is_draft, logo_url=company.logo_url, cover_url=company.cover_url,
        description=company.description, industry_id=company.industry_id, industry_name=industry_name,
        size=company.size, website=company.website, address=company.address, job_count=len(job_cards),
        created_at=company.created_at, jobs=job_cards,
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
