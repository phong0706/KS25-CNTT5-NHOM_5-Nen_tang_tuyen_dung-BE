"""API theo dõi công ty dành cho ứng viên."""
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.company_follow import CompanyFollow
from app.models.job import Job
from app.models.user import User
from app.schemas.company_follow import (
    CompanyFollowResultOut,
    FollowedCompaniesListOut,
    FollowedCompanyOut,
)

router = APIRouter(
    prefix="/candidate/followed-companies", tags=["Candidate Followed Companies"]
)


@router.get("", response_model=FollowedCompaniesListOut, summary="Danh sách công ty đang theo dõi")
def list_followed_companies(
    q: str = Query("", max_length=120, description="Tìm theo tên công ty"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    filters = [
        CompanyFollow.user_id == current_user.id,
        Company.is_visible.is_(True),
        Company.is_draft.is_(False),
    ]
    if q.strip():
        filters.append(Company.name.ilike(f"%{q.strip()}%"))

    base = (
        select(CompanyFollow, Company)
        .join(Company, Company.id == CompanyFollow.company_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(CompanyFollow.followed_at.desc(), CompanyFollow.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    company_ids = [company.id for _, company in rows]
    job_counts = {}
    if company_ids:
        job_counts = dict(
            db.execute(
                select(Job.company_id, func.count(Job.id))
                .where(Job.company_id.in_(company_ids), Job.status == "published")
                .group_by(Job.company_id)
            ).all()
        )

    items = [
        FollowedCompanyOut(
            id=company.id,
            name=company.name,
            slug=company.slug,
            logo=company.logo_url or company.logo,
            tagline=company.tagline,
            followed_at=follow.followed_at,
            active_jobs_count=int(job_counts.get(company.id, 0)),
        )
        for follow, company in rows
    ]
    return FollowedCompaniesListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.post(
    "/{company_id}",
    response_model=CompanyFollowResultOut,
    summary="Theo dõi công ty",
)
def follow_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    company = db.get(Company, company_id)
    if company is None or not company.is_visible or company.is_draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Công ty không tồn tại"
        )

    existing = db.scalar(
        select(CompanyFollow.id).where(
            CompanyFollow.user_id == current_user.id,
            CompanyFollow.company_id == company_id,
        )
    )
    if existing is None:
        db.add(CompanyFollow(user_id=current_user.id, company_id=company_id))
        db.commit()

    return CompanyFollowResultOut(
        company_id=company_id, is_following=True, message="Đã theo dõi công ty"
    )


@router.delete(
    "/{company_id}",
    response_model=CompanyFollowResultOut,
    summary="Bỏ theo dõi công ty",
)
def unfollow_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    existing = db.scalar(
        select(CompanyFollow).where(
            CompanyFollow.user_id == current_user.id,
            CompanyFollow.company_id == company_id,
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()

    return CompanyFollowResultOut(
        company_id=company_id, is_following=False, message="Đã bỏ theo dõi công ty"
    )
