"""Gửi thông báo việc làm mới cho follower bằng BackgroundTasks nội bộ."""
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import time
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.company_follow import CompanyFollow
from app.models.notification import Notification

logger = logging.getLogger(__name__)
NOTIFICATION_TYPE = "NEW_JOB_FROM_FOLLOWED_COMPANY"
BATCH_SIZE = 500
MAX_RETRIES = 3


@dataclass(frozen=True)
class PublishedJobEvent:
    job_id: int
    company_id: int
    company_name: str
    job_title: str
    location: str | None
    salary_min: int | None
    salary_max: int | None
    is_salary_negotiable: bool
    published_at: datetime


def send_followed_company_job_notifications(
    event: PublishedJobEvent,
    session_factory: Callable[[], Session] = SessionLocal,
) -> int:
    """Gửi in-app theo lô; unique dedupe_key bảo đảm an toàn khi retry."""
    last_candidate_id = 0
    sent = 0
    while True:
        db = session_factory()
        try:
            candidate_ids = list(
                db.scalars(
                    select(CompanyFollow.candidate_id)
                    .where(
                        CompanyFollow.company_id == event.company_id,
                        CompanyFollow.candidate_id > last_candidate_id,
                        CompanyFollow.created_at <= event.published_at,
                    )
                    .order_by(CompanyFollow.candidate_id.asc())
                    .limit(BATCH_SIZE)
                ).all()
            )
        finally:
            db.close()
        if not candidate_ids:
            break

        dedupe_key = f"followed-company-job:{event.job_id}"
        payload = {
            "jobId": event.job_id,
            "companyId": event.company_id,
            "companyName": event.company_name,
            "jobTitle": event.job_title,
            "location": event.location,
            "salaryMin": event.salary_min,
            "salaryMax": event.salary_max,
            "isSalaryNegotiable": event.is_salary_negotiable,
        }
        salary = (
            "Thỏa thuận"
            if event.is_salary_negotiable
            else _format_salary(event.salary_min, event.salary_max)
        )
        details = " · ".join(value for value in (event.location, salary) if value)
        message = f"{event.company_name} vừa đăng tin {event.job_title}"
        if details:
            message = f"{message} ({details})."
        else:
            message = f"{message}."
        link = f"/pages/job-detail.html?id={event.job_id}"

        for attempt in range(MAX_RETRIES):
            db = session_factory()
            try:
                existing = set(
                    db.scalars(
                        select(Notification.user_id).where(
                            Notification.user_id.in_(candidate_ids),
                            Notification.dedupe_key == dedupe_key,
                        )
                    ).all()
                )
                db.add_all(
                    [
                        Notification(
                            user_id=candidate_id,
                            type=NOTIFICATION_TYPE,
                            title=f"{event.company_name} có tin tuyển dụng mới",
                            message=message,
                            link=link,
                            ref_type="job",
                            ref_id=event.job_id,
                            payload_json=json.dumps(payload, ensure_ascii=False),
                            dedupe_key=dedupe_key,
                        )
                        for candidate_id in candidate_ids
                        if candidate_id not in existing
                    ]
                )
                db.commit()
                sent += len(candidate_ids) - len(existing)
                break
            except Exception:
                db.rollback()
                logger.exception(
                    "company_job_notification_batch_failed job_id=%s attempt=%s",
                    event.job_id,
                    attempt + 1,
                )
                if attempt + 1 == MAX_RETRIES:
                    raise
                time.sleep(0.25 * (2**attempt))
            finally:
                db.close()

        last_candidate_id = candidate_ids[-1]

    logger.info(
        "company_job_notifications_complete job_id=%s company_id=%s sent=%s",
        event.job_id,
        event.company_id,
        sent,
    )
    return sent


def _format_salary(salary_min: int | None, salary_max: int | None) -> str | None:
    if salary_min is not None and salary_max is not None:
        return f"{salary_min:,}–{salary_max:,} VNĐ"
    if salary_min is not None:
        return f"Từ {salary_min:,} VNĐ"
    if salary_max is not None:
        return f"Đến {salary_max:,} VNĐ"
    return None
