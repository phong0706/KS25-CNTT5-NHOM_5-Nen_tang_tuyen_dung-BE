"""Dịch vụ chi tiết việc làm công khai, thống kê trang chủ và lưu tin."""
from datetime import datetime, timedelta, timezone
import re
import statistics

from fastapi import HTTPException, status as http_status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaCategory, MetaSkill, SavedJob
from app.models.user import User
from app.schemas.job import FeaturedCompanyOut, HomeStatsOut

_AUTO_PROSE_PATTERNS = (
    re.compile(r"^Tuyển dụng vị trí .+ tại .+\.?$", re.IGNORECASE),
    re.compile(r"^Tối thiểu 1 năm kinh nghiệm thực tế\.?$", re.IGNORECASE),
    re.compile(r"^(?:Đang cập nhật|Chưa có mô tả)\.{0,3}$", re.IGNORECASE),
)


def _clean_real_prose(value: str | None) -> str | None:
    """Loại bỏ câu mô tả/yêu cầu tự sinh hoặc giữ chỗ để UI ẩn mục thiếu dữ liệu."""
    text = (value or "").strip()
    if not text or any(p.match(text) for p in _AUTO_PROSE_PATTERNS):
        return None
    return text


def get_featured_companies_data(db: Session, limit: int) -> list[FeaturedCompanyOut]:
    stmt = (
        select(Company.id, Company.name, Company.slug, func.count(Job.id).label("job_count"))
        .join(Job, and_(Job.company_id == Company.id, Job.status == "published"))
        .where(Company.is_draft == False)  # noqa: E712
        .group_by(Company.id, Company.slug)
        .having(func.count(Job.id) > 0)
        .order_by(func.count(Job.id).desc(), Company.id.asc())
        .limit(limit)
    )
    return [
        FeaturedCompanyOut(id=r.id, name=r.name, slug=r.slug, job_count=int(r.job_count))
        for r in db.execute(stmt).all()
    ]


def get_home_stats_data(db: Session) -> HomeStatsOut:
    total_published = int(db.scalar(select(func.count(Job.id)).where(Job.status == "published")) or 0)
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = int(
        db.scalar(
            select(func.count(Job.id)).where(
                Job.status == "published",
                func.coalesce(Job.published_at, Job.created_at) >= today_start,
            )
        ) or 0
    )
    weekly_new = int(
        db.scalar(
            select(func.count(Job.id)).where(
                Job.status == "published",
                func.coalesce(Job.published_at, Job.created_at) >= now_utc - timedelta(days=7),
            )
        ) or 0
    )
    total_companies = int(db.scalar(select(func.count(Company.id)).where(Company.is_draft == False)) or 0)  # noqa: E712
    salary_rows = db.execute(select(Job.salary_min, Job.salary_max).where(Job.status == "published")).all()
    mids = [
        (s_min + s_max) / 2 if (s_min and s_max) else (s_min or s_max)
        for s_min, s_max in salary_rows if (s_min or s_max)
    ]
    return HomeStatsOut(
        total_published_jobs=total_published,
        today_new_jobs=today_new,
        total_companies=total_companies,
        weekly_new_jobs=weekly_new,
        salary_median=int(statistics.median(mids)) if mids else 0,
        total_skills=int(db.scalar(select(func.count(MetaSkill.id))) or 0),
    )


def toggle_saved_job_action(db: Session, job_id: int, current_user: User) -> dict:
    job = db.get(Job, job_id)
    if not job or job.status != "published":
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng")
    existing = db.scalar(select(SavedJob).where(SavedJob.user_id == current_user.id, SavedJob.job_id == job_id))
    if existing:
        db.delete(existing)
        db.commit()
        return {"job_id": job_id, "is_saved": False, "message": "Đã bỏ lưu tin tuyển dụng"}
    db.add(SavedJob(user_id=current_user.id, job_id=job_id))
    db.commit()
    return {"job_id": job_id, "is_saved": True, "message": "Đã lưu tin tuyển dụng"}


def get_public_job_detail_data(db: Session, job_id: int, user: User | None) -> dict:
    stmt = (
        select(
            Job,
            Company.name.label("company_name"),
            Company.slug.label("company_slug"),
            Company.size.label("company_size"),
            Company.address.label("company_address"),
            Company.website.label("company_website"),
            Company.is_verified.label("company_is_verified"),
            Company.is_visible.label("company_is_visible"),
            Company.verification_status.label("company_verification_status"),
            Company.status.label("company_status"),
            case((Company.logo_status.in_(["approved", "active"]), Company.logo_url), else_=None).label("company_logo"),
            MetaCategory.name.label("category_name"),
            MetaCategory.slug.label("category_slug"),
        )
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .where(
            Job.id == job_id,
            Job.deleted_at.is_(None),
        )
    )
    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng")

    job = row.Job
    if job.status not in ("published", "open"):
        can_view = user and (user.id == job.employer_id or user.role in ("admin", "operator"))
        if not can_view:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng")
    skills = job.skills if isinstance(job.skills, list) else []
    is_saved = False
    applied = False
    if user is not None:
        is_saved = db.scalar(select(SavedJob.id).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id)) is not None
        applied = db.scalar(
            select(Application.id).where(
                Application.candidate_id == user.id,
                Application.job_id == job_id,
                Application.status.notin_(["withdrawn", "WITHDRAWN"]),
            )
        ) is not None

    can_manage_comp = bool(user and (user.id == job.employer_id or getattr(user, "role", "") in ("admin", "operator")))
    comp_slug = row.company_slug if (row.company_is_visible or can_manage_comp) else None

    return {
        "id": job.id,
        "status": job.status,
        "title": (job.title or "").replace("[Seed] ", "").replace("[Seed]", ""),
        "company_id": job.company_id or job.employer_id,
        "company_slug": comp_slug,
        "company_name": row.company_name or "Doanh nghiệp tuyển dụng",
        "company_logo": row.company_logo or None,
        "location": job.location,
        "type": job.work_type if getattr(job, "work_type", None) else "Toàn thời gian",
        "work_type": job.work_type if getattr(job, "work_type", None) else "Toàn thời gian",
        "employment_type": getattr(job, "job_type", None) or "Toàn thời gian",
        "level": job.level or "Tất cả",
        "experience": getattr(job, "experience_level", None) or "",
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "is_salary_negotiable": job.is_salary_negotiable,
        "description": _clean_real_prose(job.description),
        "requirements": _clean_real_prose(job.requirements),
        "benefits": "\n".join(job.benefits) if isinstance(job.benefits, list) else (_clean_real_prose(job.benefits) or ""),
        "skills": skills,
        "category_id": job.category_id,
        "category_name": row.category_name,
        "category_slug": row.category_slug,
        "quantity": job.quantity,
        "deadline": job.deadline,
        "created_at": job.created_at,
        "published_at": job.published_at,
        "is_saved": is_saved,
        "applied": applied,
        "company_is_verified": bool(
            row.company_is_verified
            or str(row.company_status or "").upper() in ("VERIFIED", "COMPANYSTATUS.VERIFIED")
            or row.company_verification_status == "da_xac_minh"
        ),
        "company_size": row.company_size,
        "company_address": row.company_address,
        "company_website": row.company_website,
    }
