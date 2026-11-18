"""API theo dõi công ty dành cho ứng viên."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.crud import company_follow as repository
from app.db.session import get_db
from app.models.user import User
from app.schemas.company_follow import (
    CompanyFollowItemOut,
    CompanyFollowListData,
    CompanyFollowListMeta,
    CompanyFollowListOut,
    CompanyFollowMutationData,
    CompanyFollowMutationOut,
    CompanyFollowStatusData,
    CompanyFollowStatusOut,
)
from app.services.company_follow import follow_company, get_follow_status, unfollow_company

router = APIRouter(tags=["Company Follows"])


@router.post(
    "/companies/{company_id}/follow",
    response_model=CompanyFollowMutationOut,
    summary="Theo dõi công ty (idempotent)",
)
def follow_company_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    follow_company(db, current_user.id, company_id)
    return CompanyFollowMutationOut(
        data=CompanyFollowMutationData(company_id=company_id, is_following=True),
        message="Đã theo dõi công ty.",
    )


@router.delete(
    "/companies/{company_id}/follow",
    response_model=CompanyFollowMutationOut,
    summary="Bỏ theo dõi công ty (idempotent)",
)
def unfollow_company_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    unfollow_company(db, current_user.id, company_id)
    return CompanyFollowMutationOut(
        data=CompanyFollowMutationData(company_id=company_id, is_following=False),
        message="Đã bỏ theo dõi công ty.",
    )


@router.get(
    "/companies/{company_id}/follow-status",
    response_model=CompanyFollowStatusOut,
    summary="Kiểm tra trạng thái theo dõi công ty",
)
def company_follow_status_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    following, count = get_follow_status(db, current_user.id, company_id)
    return CompanyFollowStatusOut(
        data=CompanyFollowStatusData(
            company_id=company_id,
            is_following=following,
            follower_count=count,
        ),
        message="Đã lấy trạng thái theo dõi.",
    )


@router.get(
    "/candidates/me/followed-companies",
    response_model=CompanyFollowListOut,
    summary="Danh sách công ty đang theo dõi",
)
def list_followed_companies_endpoint(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    keyword: str | None = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    normalized_keyword = keyword.strip() if keyword else None
    rows, total = repository.list_followed_companies(
        db, current_user.id, page, limit, normalized_keyword
    )
    items = [
        CompanyFollowItemOut(
            id=row.id,
            name=row.name,
            logo=row.logo_url or row.logo,
            industry=row.industry_name,
            location=row.address,
            active_job_count=int(row.job_count or 0),
            followed_at=row.followed_at,
        )
        for row in rows
    ]
    return CompanyFollowListOut(
        data=CompanyFollowListData(items=items),
        message="Đã lấy danh sách công ty đang theo dõi.",
        meta=CompanyFollowListMeta(page=page, limit=limit, total=total),
    )
