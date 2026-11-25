"""Router bổ sung cho Mega Menu, Tools & Phỏng vấn."""
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy import and_, func, select, desc
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models.job import Job, MetaCategory, MetaLocation, MetaLevel, JobApplication
from app.models.user import User
from app.core.security import get_optional_user

router = APIRouter(tags=["Meta & Navigation"])

class NavCategoryItem(BaseModel):
    id: int
    slug: str
    name: str
    icon: str = "code"
    job_count: int

class NavLocationItem(BaseModel):
    id: int
    slug: str
    name: str
    job_count: int

class MetaNavResponse(BaseModel):
    total_jobs: int
    tax_effective: str = "11/2026"
    unread_applications_count: int = 0
    by_category: List[NavCategoryItem]
    by_location: List[NavLocationItem]

@router.get("/api/meta/nav", response_model=MetaNavResponse, summary="Top ngành nghề và địa điểm cho Mega Menu")
def get_mega_nav_meta(
    response: Response,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Trả về dữ liệu động cho Mega Menu: tổng số tin, top ngành nghề & địa điểm có job_count > 0, badge cập nhật."""
    response.headers["Cache-Control"] = "public, max-age=60"

    # Tổng số tin tuyển dụng đang mở
    total_jobs = db.scalar(select(func.count(Job.id)).where(Job.status == "published")) or 0

    # Top ngành nghề theo job_count
    cat_stmt = (
        select(
            MetaCategory.id,
            MetaCategory.slug,
            MetaCategory.name,
            MetaCategory.icon,
            func.count(Job.id).label("job_count"),
        )
        .join(Job, and_(Job.category_id == MetaCategory.id, Job.status == "published"))
        .group_by(MetaCategory.id, MetaCategory.slug, MetaCategory.name, MetaCategory.icon)
        .having(func.count(Job.id) > 0)
        .order_by(desc("job_count"), MetaCategory.name.asc())
        .limit(10)
    )
    cats = [
        NavCategoryItem(
            id=r.id,
            slug=r.slug,
            name=r.name,
            icon=r.icon or "code",
            job_count=int(r.job_count)
        ) for r in db.execute(cat_stmt).all()
    ]

    # Top địa điểm theo job_count
    loc_stmt = (
        select(
            MetaLocation.id,
            MetaLocation.slug,
            MetaLocation.name,
            func.count(Job.id).label("job_count"),
        )
        .join(Job, and_(Job.location_id == MetaLocation.id, Job.status == "published"))
        .group_by(MetaLocation.id, MetaLocation.slug, MetaLocation.name)
        .having(func.count(Job.id) > 0)
        .order_by(desc("job_count"), MetaLocation.name.asc())
        .limit(10)
    )
    locs = [
        NavLocationItem(
            id=r.id,
            slug=r.slug,
            name=r.name,
            job_count=int(r.job_count)
        ) for r in db.execute(loc_stmt).all()
    ]

    unread_count = 0
    if user and user.role == "candidate":
        try:
            unread_count = db.scalar(
                select(func.count(JobApplication.id)).where(
                    JobApplication.candidate_id == user.id,
                    JobApplication.is_viewed == False
                )
            ) or 0
        except Exception:
            unread_count = 0

    return MetaNavResponse(
        total_jobs=total_jobs,
        tax_effective="11/2026",
        unread_applications_count=unread_count,
        by_category=cats,
        by_location=locs
    )
