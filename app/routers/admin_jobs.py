"""Router quản trị viên duyệt & quản lý tin tuyển dụng (<= 160 dòng)."""
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.schemas.job_moderation import (
    AdminJobDeleteIn,
    AdminJobDetailOut,
    AdminJobListItemOut,
    AdminJobsListOut,
    JobModerationActionIn,
    JobModerationOut,
    JobRejectActionIn,
)
from app.services.job_moderation_service import (
    admin_delete_job_service,
    approve_job_service,
    reject_job_service,
)

router = APIRouter(prefix="/admin/jobs", tags=["Admin Jobs"])


@router.get("", response_model=AdminJobsListOut)
def list_admin_jobs(
    status_filter: str = Query("pending", alias="status"),
    search: str = Query("", alias="q"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Lấy danh sách tin tuyển dụng cho admin duyệt.
    
    Tin chưa xóa (deleted_at IS NULL). Nếu pending thì sắp tin cũ nhất lên đầu.
    """
    query = (
        select(Job, Company.name.label("comp_name"), User.email.label("emp_email"), User.full_name.label("emp_name"))
        .outerjoin(Company, Job.company_id == Company.id)
        .join(User, Job.employer_id == User.id)
        .where(Job.deleted_at.is_(None))
    )

    if status_filter and status_filter != "all":
        if status_filter in ("open", "published"):
            query = query.where(Job.status.in_(["open", "published"]))
        else:
            query = query.where(Job.status == status_filter)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.where(Job.title.ilike(term) | Company.name.ilike(term))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    offset = (page - 1) * limit

    # Nếu đang xem tab pending -> sắp tin cũ nhất lên đầu (FIFO để duyệt trước)
    order_clause = Job.created_at.asc() if status_filter == "pending" else Job.created_at.desc()
    results = db.execute(query.order_by(order_clause).offset(offset).limit(limit)).all()

    # Thống kê số lượng theo từng tab (chỉ tính tin chưa xóa)
    raw_counts = dict(
        db.execute(
            select(Job.status, func.count(Job.id))
            .where(Job.deleted_at.is_(None))
            .group_by(Job.status)
        ).all()
    )
    published_cnt = raw_counts.get("published", 0) + raw_counts.get("open", 0)
    logo_pending_cnt = db.scalar(
        select(func.count(Company.id))
        .where(Company.logo.is_not(None), Company.logo != "", Company.logo_status.in_(["pending", "pending_review"]))
    ) or 0
    counts = {
        "pending": raw_counts.get("pending", 0),
        "published": published_cnt,
        "open": published_cnt,
        "rejected": raw_counts.get("rejected", 0),
        "closed": raw_counts.get("closed", 0),
        "logo_pending": logo_pending_cnt,
        "all": sum(raw_counts.values()),
    }

    items = [
        AdminJobListItemOut(
            id=job.id,
            title=job.title,
            company_name=comp_name or "Chưa gắn công ty",
            employer_email=emp_email,
            employer_name=emp_name,
            status=job.status,
            version=job.version,
            deadline=job.deadline,
            created_at=job.created_at,
        )
        for job, comp_name, emp_email, emp_name in results
    ]
    return AdminJobsListOut(items=items, total=total, counts=counts)


@router.get("/{job_id}", response_model=AdminJobDetailOut)
def get_admin_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Xem chi tiết một tin tuyển dụng."""
    stmt = (
        select(Job, Company.name.label("comp_name"), User.email.label("emp_email"), User.full_name.label("emp_name"))
        .outerjoin(Company, Job.company_id == Company.id)
        .join(User, Job.employer_id == User.id)
        .where(Job.id == job_id, Job.deleted_at.is_(None))
    )
    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng.")
    job, comp_name, emp_email, emp_name = row
    return AdminJobDetailOut(
        id=job.id,
        title=job.title,
        company_name=comp_name or "Chưa gắn công ty",
        employer_email=emp_email,
        employer_name=emp_name,
        status=job.status,
        version=job.version,
        location=job.location,
        work_type=job.work_type,
        level=job.level,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        is_salary_negotiable=job.is_salary_negotiable,
        deadline=job.deadline,
        skills=job.skills,
        description=job.description,
        requirements=job.requirements,
        review_note=job.review_note,
        created_at=job.created_at,
        published_at=job.published_at,
    )


@router.post("/{job_id}/approve", response_model=JobModerationOut)
def admin_approve_job(
    job_id: int,
    payload: JobModerationActionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Admin duyệt tin tuyển dụng."""
    return approve_job_service(
        db=db,
        job_id=job_id,
        admin_id=admin.id,
        expected_version=payload.version,
    )


@router.post("/{job_id}/reject", response_model=JobModerationOut)
def admin_reject_job(
    job_id: int,
    payload: JobRejectActionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Admin từ chối tin tuyển dụng kèm lý do."""
    return reject_job_service(
        db=db,
        job_id=job_id,
        admin_id=admin.id,
        expected_version=payload.version,
        reason=payload.reason,
    )


@router.delete("/{job_id}", response_model=JobModerationOut)
def admin_delete_job(
    job_id: int,
    payload: AdminJobDeleteIn = Body(default_factory=AdminJobDeleteIn),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    """Admin xóa mềm tin tuyển dụng (bắt buộc lý do nếu tin đang chờ duyệt)."""
    return admin_delete_job_service(
        db=db,
        job_id=job_id,
        admin_id=admin.id,
        reason=payload.reason,
    )
