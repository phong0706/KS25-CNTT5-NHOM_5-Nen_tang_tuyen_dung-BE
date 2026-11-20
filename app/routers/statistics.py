"""Router thống kê Dashboard cho Nhà tuyển dụng và Admin.

Endpoints:
- GET /api/employer/dashboard/stats - Thống kê Dashboard Nhà tuyển dụng
- GET /api/admin/dashboard/stats - Thống kê Dashboard Admin

Hỗ trợ lọc khoảng thời gian qua query params `from_date` và `to_date`.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.application import Application, Interview
from app.models.catalog import Industry
from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaCategory
from app.models.user import User

router = APIRouter(tags=["Dashboard Statistics"])


# ============================================================
# Pydantic Models for Response
# ============================================================

class EmployerStatsOut(BaseModel):
    """Thống kê Dashboard Nhà tuyển dụng."""
    total_jobs: int
    active_jobs: int
    draft_jobs: int
    closed_jobs: int
    total_views: int = Field(description="Lượt xem tích lũy; hệ thống chưa lưu lịch sử xem theo ngày.")
    total_applications: int
    applications_by_status: dict[str, int]
    unviewed_applications: int
    hiring_rate: float
    upcoming_interviews: int
    period_jobs_created: int


class AdminStatsOut(BaseModel):
    """Thống kê Dashboard Admin."""
    total_users: int
    users_by_role: dict[str, int]
    active_users: int
    new_users_in_period: int
    total_companies: int
    verified_companies: int
    pending_companies: int
    companies_by_industry: list[dict]
    total_jobs: int
    jobs_by_industry: list[dict]
    jobs_by_status: dict[str, int]
    applications_by_day: list[dict]
    total_applications: int


# ============================================================
# Helper Functions
# ============================================================

def _parse_date_range(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> tuple[Optional[date], Optional[date]]:
    """Parse và validate khoảng thời gian."""
    parsed_from = None
    parsed_to = None

    if from_date:
        try:
            parsed_from = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Định dạng from_date không hợp lệ. Sử dụng YYYY-MM-DD.")

    if to_date:
        try:
            parsed_to = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Định dạng to_date không hợp lệ. Sử dụng YYYY-MM-DD.")

    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise HTTPException(status_code=400, detail="from_date không được lớn hơn to_date.")

    return parsed_from, parsed_to


def _apply_date_range(query, column, parsed_from: date | None, parsed_to: date | None):
    """Áp dụng khoảng ngày bao gồm cả ngày kết thúc, không phụ thuộc độ chính xác timestamp."""
    if parsed_from:
        query = query.where(column >= datetime.combine(parsed_from, time.min))
    if parsed_to:
        if parsed_to == date.max:
            query = query.where(column <= datetime.max)
        else:
            query = query.where(column < datetime.combine(parsed_to + timedelta(days=1), time.min))
    return query


# ============================================================
# EMPLOYER DASHBOARD STATISTICS
# ============================================================

@router.get("/employer/dashboard/stats", response_model=EmployerStatsOut, summary="Thống kê Dashboard Nhà tuyển dụng")
def get_employer_dashboard_stats(
    from_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer", "recruiter")),
) -> EmployerStatsOut:
    """Thống kê Dashboard Nhà tuyển dụng: số tin, lượt xem, hồ sơ theo trạng thái, tỉ lệ trúng tuyển."""
    employer_id = current_user.id
    parsed_from, parsed_to = _parse_date_range(from_date, to_date)

    # Số tin và lượt xem là ảnh chụp hiện tại/tích lũy; DB không lưu lịch sử
    # trạng thái tin hoặc lượt xem theo ngày.
    job_status_query = (
        select(
            func.lower(Job.status),
            func.count(Job.id),
            func.coalesce(func.sum(Job.views_count), 0),
        )
        .where(
            Job.employer_id == employer_id,
            Job.deleted_at.is_(None),
        )
        .group_by(func.lower(Job.status))
    )
    job_status_rows = db.execute(job_status_query).all()
    total_jobs = sum(row[1] for row in job_status_rows)
    job_status_counts: dict[str, int] = {}
    for row in job_status_rows:
        normalized_status = row[0] or "unknown"
        job_status_counts[normalized_status] = job_status_counts.get(normalized_status, 0) + row[1]

    active_jobs = job_status_counts.get("published", 0) + job_status_counts.get("open", 0)
    draft_jobs = job_status_counts.get("draft", 0)
    closed_jobs = job_status_counts.get("closed", 0)
    total_views = sum(row[2] for row in job_status_rows)

    # 1. Trạng thái tin tuyển dụng hiện tại
    # 2. Hồ sơ trong khoảng ngày đã chọn
    employer_job_ids = select(Job.id).where(
        Job.employer_id == employer_id,
        Job.deleted_at.is_(None),
    )
    total_applications = 0
    applications_by_status: dict[str, int] = {}
    unviewed_applications = 0
    hiring_rate = 0.0

    if total_jobs:
        applications_filter = Application.job_id.in_(employer_job_ids)
        total_applications_query = _apply_date_range(
            select(func.count(Application.id)).where(applications_filter),
            Application.created_at,
            parsed_from,
            parsed_to,
        )
        total_applications = db.scalar(total_applications_query) or 0

        status_query = _apply_date_range(
            select(
                func.lower(Application.status),
                func.count(Application.id).label("count"),
            )
            .where(applications_filter)
            .group_by(func.lower(Application.status)),
            Application.created_at,
            parsed_from,
            parsed_to,
        )
        status_rows = db.execute(status_query).all()
        for row in status_rows:
            normalized_status = row[0] or "unknown"
            applications_by_status[normalized_status] = (
                applications_by_status.get(normalized_status, 0) + row[1]
            )
        unviewed_query = _apply_date_range(
            select(func.count(Application.id))
            .where(applications_filter, Application.viewed_at.is_(None)),
            Application.created_at,
            parsed_from,
            parsed_to,
        )
        unviewed_applications = db.scalar(unviewed_query) or 0
        offered_count = applications_by_status.get("offered", 0)
        hiring_rate = round((offered_count / total_applications * 100), 2) if total_applications > 0 else 0.0

    # 3. Lịch phỏng vấn sắp tới là số lịch từ hiện tại trở đi, độc lập
    # với khoảng ngày dùng để lọc hoạt động đã phát sinh.
    upcoming_interviews = db.scalar(
        select(func.count(Interview.id))
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.employer_id == employer_id,
            Interview.scheduled_at >= datetime.now(),
            func.lower(Interview.status) == "scheduled",
        )
    ) or 0

    # 4. Số tin được tạo trong khoảng ngày đã chọn.
    period_job_query = select(func.count(Job.id)).where(
        Job.employer_id == employer_id,
        Job.deleted_at.is_(None),
    )
    period_job_query = _apply_date_range(
        period_job_query,
        Job.created_at,
        parsed_from,
        parsed_to,
    )
    period_jobs_created = db.scalar(period_job_query) or 0

    return EmployerStatsOut(
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        draft_jobs=draft_jobs,
        closed_jobs=closed_jobs,
        total_views=total_views,
        total_applications=total_applications,
        applications_by_status=applications_by_status,
        unviewed_applications=unviewed_applications,
        hiring_rate=hiring_rate,
        upcoming_interviews=upcoming_interviews,
        period_jobs_created=period_jobs_created,
    )


# ============================================================
# ADMIN DASHBOARD STATISTICS
# ============================================================

@router.get("/admin/dashboard/stats", response_model=AdminStatsOut, summary="Thống kê Dashboard Admin")
def get_admin_dashboard_stats(
    from_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
) -> AdminStatsOut:
    """Thống kê Dashboard Admin: người dùng theo vai trò, công ty, tin theo ngành, hồ sơ theo ngày."""
    parsed_from, parsed_to = _parse_date_range(from_date, to_date)

    # Counts by role and account/company/job statuses are current snapshots;
    # the date range applies to creation/submission activity below.
    total_users = db.scalar(select(func.count(User.id))) or 0
    role_rows = db.execute(select(User.role, func.count(User.id).label("count")).group_by(User.role)).all()
    users_by_role = {row[0]: row[1] for row in role_rows}
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0

    new_users_query = _apply_date_range(
        select(func.count(User.id)),
        User.created_at,
        parsed_from,
        parsed_to,
    )
    new_users_in_period = db.scalar(new_users_query) or 0

    # 2. Công ty
    total_companies = db.scalar(
        select(func.count(Company.id)).where(Company.is_draft.is_(False))
    ) or 0
    verified_companies = db.scalar(
        select(func.count(Company.id)).where(
            Company.is_draft.is_(False),
            Company.is_verified.is_(True),
        )
    ) or 0
    pending_companies = db.scalar(
        select(func.count(Company.id)).where(
            Company.is_draft.is_(False),
            Company.is_verified.is_(False),
            Company.status == CompanyStatus.PENDING,
        )
    ) or 0

    industries = {industry.id: industry.name for industry in db.scalars(select(Industry)).all()}
    categories = {category.id: category.name for category in db.scalars(select(MetaCategory)).all()}

    # Công ty theo ngành nghề khai báo trên hồ sơ công ty.
    companies_by_industry_query = (
        select(Company.industry_id, func.count(Company.id).label("count"))
        .where(
            Company.is_draft.is_(False),
            Company.is_verified.is_(True),
            Company.industry_id.is_not(None),
        )
        .group_by(Company.industry_id)
        .order_by(func.count(Company.id).desc())
    )
    companies_by_industry_query = _apply_date_range(
        companies_by_industry_query,
        Company.created_at,
        parsed_from,
        parsed_to,
    )
    companies_by_industry_rows = db.execute(companies_by_industry_query).all()

    companies_by_industry = [
        {
            "industry_id": row[0],
            "industry_name": industries.get(row[0], "Chưa phân loại"),
            "count": row[1],
        }
        for row in companies_by_industry_rows
    ]

    # 3. Tin tuyển dụng
    total_jobs = db.scalar(select(func.count(Job.id)).where(Job.deleted_at.is_(None))) or 0

    jobs_by_industry_query = (
        select(
            Job.category_id,
            func.count(Job.id).label("count")
        )
        .where(
            Job.deleted_at.is_(None),
            Job.category_id.is_not(None),
        )
        .group_by(Job.category_id)
        .order_by(func.count(Job.id).desc())
    )
    jobs_by_industry_query = _apply_date_range(
        jobs_by_industry_query,
        Job.created_at,
        parsed_from,
        parsed_to,
    )
    jobs_by_industry_rows = db.execute(jobs_by_industry_query).all()

    jobs_by_industry = [
        {
            "category_id": row[0],
            "category_name": categories.get(row[0], "Chưa phân loại"),
            "count": row[1],
        }
        for row in jobs_by_industry_rows
    ]

    normalized_job_status = func.lower(Job.status)
    job_status_rows = db.execute(
        select(normalized_job_status, func.count(Job.id).label("count"))
        .where(Job.deleted_at.is_(None))
        .group_by(normalized_job_status)
    ).all()
    jobs_by_status = {row[0]: row[1] for row in job_status_rows}

    # 4. Hồ sơ theo ngày
    app_day_query = (
        select(
            func.date(Application.created_at).label("date"),
            func.count(Application.id).label("count")
        )
        .group_by(func.date(Application.created_at))
        .order_by(func.date(Application.created_at))
    )
    app_day_query = _apply_date_range(
        app_day_query,
        Application.created_at,
        parsed_from,
        parsed_to,
    )

    app_day_rows = db.execute(app_day_query).all()

    applications_by_day = [
        {
            "date": row[0].isoformat() if isinstance(row[0], date) else str(row[0]),
            "count": row[1],
        }
        for row in app_day_rows
    ]

    # Total follows the selected date range (all-time when no range is supplied).
    total_applications_query = _apply_date_range(
        select(func.count(Application.id)),
        Application.created_at,
        parsed_from,
        parsed_to,
    )
    total_applications = db.scalar(total_applications_query) or 0

    return AdminStatsOut(
        total_users=total_users,
        users_by_role=users_by_role,
        active_users=active_users,
        new_users_in_period=new_users_in_period,
        total_companies=total_companies,
        verified_companies=verified_companies,
        pending_companies=pending_companies,
        companies_by_industry=companies_by_industry,
        total_jobs=total_jobs,
        jobs_by_industry=jobs_by_industry,
        jobs_by_status=jobs_by_status,
        applications_by_day=applications_by_day,
        total_applications=total_applications,
    )