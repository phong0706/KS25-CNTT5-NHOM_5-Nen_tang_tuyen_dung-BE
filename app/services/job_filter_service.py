"""job_filter_service.py - Định nghĩa chuẩn hóa duy nhất cho việc làm 'đang tuyển' trong TechRecruit (< 100 dòng).
Bao gồm: status == 'published', Company.is_visible == True, deadline >= today (hoặc None), không phải tin test.
"""
from datetime import date
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job


def open_jobs_clause(company_id: int | None = None) -> list:
    """Định nghĩa chuẩn hóa duy nhất cho việc làm 'đang tuyển' toàn hệ thống."""
    conds = [
        Job.status.in_(["published", "open"]),
        Job.deleted_at.is_(None),
        or_(Job.deadline.is_(None), Job.deadline >= date.today()),
        Company.is_visible == True,  # noqa: E712
    ]
    if company_id is not None:
        conds.append(Job.company_id == company_id)
    return conds


def get_active_job_conds(company_id: int | None = None) -> list:
    """Trả về danh sách điều kiện SQLAlchemy cho hero/thống kê công khai (lọc thêm tin test)."""
    return [
        *open_jobs_clause(company_id=company_id),
        ~Job.title.regexp_match(r"(?i)^(mmmmmm|test\b|test\s+|.*test\s+job|valid\s+engineer|pending\s+engineer)"),
    ]


def count_active_jobs(db: Session, company_id: int | None = None) -> int:
    """Đếm chính xác số lượng việc làm đang tuyển chuẩn hóa toàn hệ thống."""
    stmt = (
        select(func.count(Job.id))
        .join(Company, Job.company_id == Company.id)
        .where(and_(*get_active_job_conds(company_id=company_id)))
    )
    return int(db.scalar(stmt) or 0)
