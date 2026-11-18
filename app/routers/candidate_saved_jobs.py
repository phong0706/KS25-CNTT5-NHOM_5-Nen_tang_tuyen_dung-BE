"""Router quản lý việc làm đã lưu của ứng viên (/api/candidate/saved-jobs).
Tuân thủ techrecruit-rules: kiểm tra quyền 401/403/404, idempotent, < 200 dòng.
"""
from datetime import datetime
import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job, SavedJob
from app.models.user import User
from app.schemas.job import PublicJobCardOut, SavedJobsListOut
from app.services.saved_jobs_service import compute_is_expired

router = APIRouter(prefix="/candidate/saved-jobs", tags=["Candidate Saved Jobs"])


@router.get("", response_model=SavedJobsListOut, summary="Danh sách việc làm đã lưu")
def list_saved_jobs(
    q: str = Query("", description="Tìm theo tên vị trí, công ty hoặc địa điểm"),
    sort: str = Query("newest", description="newest (lưu gần nhất) hoặc expiring_soon (sắp hết hạn)"),
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=50, description="Số lượng mỗi trang"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    stmt = (
        select(SavedJob, Job, Company.name.label("company_name"), Company.slug.label("company_slug"))
        .join(Job, SavedJob.job_id == Job.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(SavedJob.user_id == current_user.id)
    )

    kw = q.strip()
    if kw:
        stmt = stmt.where(
            or_(
                Job.title.ilike(f"%{kw}%"),
                Company.name.ilike(f"%{kw}%"),
                Job.location.ilike(f"%{kw}%"),
            )
        )

    # Đếm tổng số bản ghi
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Sắp xếp
    if sort == "expiring_soon":
        stmt = stmt.order_by(Job.deadline.asc().nulls_last(), SavedJob.created_at.desc())
    else:  # newest
        stmt = stmt.order_by(SavedJob.created_at.desc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    rows = db.execute(stmt).all()

    items: list[PublicJobCardOut] = []
    now = datetime.now()
    for row in rows:
        sj: SavedJob = row[0]
        jb: Job = row[1]
        comp_name: str = row[2] or "Công ty công nghệ"
        comp_slug: str | None = row[3]

        # Kỹ năng
        skills_list = []
        if jb.skills:
            if isinstance(jb.skills, list):
                skills_list = jb.skills
            elif isinstance(jb.skills, str):
                try:
                    parsed = json.loads(jb.skills)
                    if isinstance(parsed, list):
                        skills_list = parsed
                except Exception:
                    skills_list = [s.strip() for s in jb.skills.split(",") if s.strip()]

        expired = compute_is_expired(jb.status, jb.deadline, now=now)

        items.append(
            PublicJobCardOut(
                id=jb.id,
                title=jb.title,
                company_id=jb.company_id,
                company_slug=comp_slug,
                company_name=comp_name,
                location=jb.location,
                level=jb.level,
                work_type=jb.work_type,
                salary_min=jb.salary_min,
                salary_max=jb.salary_max,
                is_salary_negotiable=bool(jb.is_salary_negotiable),
                skills=skills_list,
                published_at=jb.published_at,
                created_at=sj.created_at or jb.created_at,
                is_saved=True,
                is_expired=expired,
                deadline=jb.deadline,
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return SavedJobsListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/{job_id}", summary="Lưu việc làm (Idempotent)")
def save_job_idempotent(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    # Kiểm tra tin tồn tại
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tin tuyển dụng không tồn tại",
        )

    existing = db.scalar(
        select(SavedJob).where(
            SavedJob.user_id == current_user.id,
            SavedJob.job_id == job_id,
        )
    )
    if not existing:
        db.add(SavedJob(user_id=current_user.id, job_id=job_id))
        db.commit()

    return {
        "job_id": job_id,
        "is_saved": True,
        "message": "Đã lưu việc làm",
    }


@router.delete("/{job_id}", summary="Bỏ lưu việc làm (Idempotent)")
def unsave_job_idempotent(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    existing = db.scalar(
        select(SavedJob).where(
            SavedJob.user_id == current_user.id,
            SavedJob.job_id == job_id,
        )
    )
    if existing:
        db.delete(existing)
        db.commit()

    return {
        "job_id": job_id,
        "is_saved": False,
        "message": "Đã bỏ lưu việc làm",
    }
