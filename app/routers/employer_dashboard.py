"""Router tổng quan tuyển dụng (/api/employer/dashboard) tính số liệu 100% từ DB theo scope."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.employer_scope import (
    EmployerScope,
    get_admin_company_scope,
    get_employer_scope,
    resolve_company_review_status,
)
from app.db.session import get_db
from app.models.application import Application, Interview
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.services.job_filter_service import open_jobs_clause

router = APIRouter(prefix="/employer/dashboard", tags=["Employer Dashboard"])


def _build_dashboard_payload(db: Session, company: Company) -> dict:
    cid = company.id
    now_utc = datetime.now(timezone.utc)

    # 1. Đếm tin đang tuyển bằng hàm dùng chung open_jobs_clause()
    open_jobs = int(
        db.scalar(
            select(func.count(Job.id))
            .join(Company, Job.company_id == Company.id)
            .where(*open_jobs_clause(company_id=cid))
        )
        or 0
    )

    # 2. Đếm các trạng thái tin theo company_id bằng GROUP BY
    job_rows = db.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.company_id == cid, Job.deleted_at.is_(None))
        .group_by(Job.status)
    ).all()
    by_job_status = {str(st): int(cnt) for st, cnt in job_rows}

    # 3. Đếm hồ sơ ứng tuyển theo company_id bằng COUNT/GROUP BY
    app_agg = db.execute(
        select(
            func.count(Application.id),
            func.coalesce(func.sum(case((Application.viewed_at.is_(None), 1), else_=0)), 0),
        )
        .join(Job, Application.job_id == Job.id)
        .where(Job.company_id == cid, Job.deleted_at.is_(None))
    ).first()
    applications_total = int(app_agg[0] or 0) if app_agg else 0
    applications_unseen = int(app_agg[1] or 0) if app_agg else 0

    app_status_rows = db.execute(
        select(Application.status, func.count(Application.id))
        .join(Job, Application.job_id == Job.id)
        .where(Job.company_id == cid, Job.deleted_at.is_(None))
        .group_by(Application.status)
    ).all()
    applications_by_status: dict[str, int] = {}
    for raw_st, cnt in app_status_rows:
        key = str(raw_st.value if hasattr(raw_st, "value") else raw_st).lower()
        key = "reviewing" if key == "screening" else key
        applications_by_status[key] = applications_by_status.get(key, 0) + int(cnt)

    # 4. Đếm lịch phỏng vấn sắp tới & lấy lịch gần nhất theo company_id
    iv_base = (
        select(Interview, Job.title, User.full_name)
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(User, Application.candidate_id == User.id)
        .where(
            Job.company_id == cid,
            Job.deleted_at.is_(None),
            Interview.status == "scheduled",
            Interview.scheduled_at >= now_utc.replace(tzinfo=None),
        )
    )
    upcoming_rows = db.execute(iv_base.order_by(Interview.scheduled_at.asc())).all()
    nearest = None
    if upcoming_rows:
        iv, job_title, cand_name = upcoming_rows[0]
        nearest = {
            "id": iv.id,
            "application_id": iv.application_id,
            "candidate_name": cand_name or "",
            "job_title": job_title or "",
            "scheduled_at": iv.scheduled_at.isoformat() if iv.scheduled_at else None,
            "mode": iv.mode,
        }

    return {
        "open_jobs": open_jobs,
        "draft_jobs": by_job_status.get("draft", 0),
        "pending_jobs": by_job_status.get("pending", 0),
        "reverify_pending_jobs": by_job_status.get("reverify_pending", 0),
        "hidden_jobs": by_job_status.get("hidden", 0),
        "closed_jobs": by_job_status.get("closed", 0),
        "applications_total": applications_total,
        "applications_unseen": applications_unseen,
        "applications_by_status": applications_by_status,
        "interviews_upcoming": {
            "count": len(upcoming_rows),
            "nearest": nearest,
        },
        "company": {
            "id": company.id,
            "name": company.name,
            "slug": company.slug,
            "review_status": resolve_company_review_status(company),
        },
        "server_time": now_utc.isoformat(),
    }


@router.get("", summary="Số liệu tổng quan tuyển dụng của công ty hiện tại")
def get_employer_dashboard(
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    return _build_dashboard_payload(db, scope.company)


@router.get("/admin", summary="Admin/Operator xem tổng quan tuyển dụng theo company_id (có AuditLog)")
def get_employer_dashboard_for_admin(
    scope: EmployerScope = Depends(get_admin_company_scope),
    db: Session = Depends(get_db),
):
    return _build_dashboard_payload(db, scope.company)
