"""Dịch vụ hỗ trợ quản lý lịch phỏng vấn (kiểm tra xung đột thời gian).
Tuân thủ: < 200 dòng.
"""
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application, Interview
from app.models.job import Job
from app.models.user import User


def check_interview_overlap(
    db: Session, employer_id: int, start: datetime, duration_min: int, exclude_id: int | None = None
) -> dict | None:
    """Kiểm tra xem lịch phỏng vấn mới có giao thoa với lịch đã có của NTD hay không."""
    end = start + timedelta(minutes=duration_min)
    stmt = (
        select(Interview, User.full_name.label("cand_name"), Job.title.label("job_title"))
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(User, Application.candidate_id == User.id)
        .where(
            Job.employer_id == employer_id,
            Interview.status == "scheduled",
        )
    )
    if exclude_id:
        stmt = stmt.where(Interview.id != exclude_id)

    for iv, c_name, j_title in db.execute(stmt).all():
        iv_start = iv.scheduled_at
        iv_end = iv_start + timedelta(minutes=iv.duration_min or 45)
        if start < iv_end and end > iv_start:
            return {
                "id": iv.id,
                "scheduled_at": iv_start,
                "duration_min": iv.duration_min,
                "candidate_name": c_name,
                "job_title": j_title,
            }
    return None
