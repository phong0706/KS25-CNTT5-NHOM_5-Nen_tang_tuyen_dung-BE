"""Service xử lý quy trình duyệt & xóa tin tuyển dụng an toàn (<= 195 dòng)."""
from datetime import datetime, timezone
import uuid
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.job_status_history import JobStatusHistory
from app.models.notification import Notification
from app.services.job_moderation_rules import (
    validate_job_transition,
    validate_optimistic_version,
    validate_rejection_reason,
)
from app.services.skill_sync_service import recalculate_all_skill_counts


def _send_moderation_notification(db: Session, uid: int, title: str, msg: str, ref_id: int) -> None:
    db.add(Notification(
        user_id=uid, title=title, message=msg, type="job_status",
        ref_type="job", ref_id=ref_id, link=f"/pages/employer/jobs.html?job={ref_id}",
        dedupe_key=f"job_mod_{ref_id}_{uuid.uuid4().hex[:6]}",
    ))


def _get_verified_job_for_employer(db: Session, job_id: int, employer_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin.")
    if job.employer_id != employer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền với tin này.")
    company = db.get(Company, job.company_id) if job.company_id else None
    is_verif = company and (
        company.verification_status == "da_xac_minh" or
        company.status == CompanyStatus.VERIFIED or
        bool(getattr(company, "is_verified", False))
    )
    if not is_verif:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="COMPANY_NOT_VERIFIED: Công ty chưa được xác minh, không thể gửi duyệt tin.",
        )
    return job


def submit_job_for_review_service(db: Session, job_id: int, employer_id: int, expected_version: int) -> Job:
    job = _get_verified_job_for_employer(db, job_id, employer_id)
    validate_job_transition(job.status, "pending", "employer")
    validate_optimistic_version(expected_version, job.version)
    old_st = job.status
    stmt = (
        update(Job).where(Job.id == job_id, Job.version == expected_version, Job.status == old_st)
        .values(status="pending", version=Job.version + 1)
    )
    if db.execute(stmt).rowcount == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VERSION_CONFLICT")
    db.add(JobStatusHistory(job_id=job.id, from_status=old_st, to_status="pending", changed_by=employer_id))
    _send_moderation_notification(db, employer_id, "Tin tuyển dụng đã gửi duyệt", f"Tin tuyển dụng '{job.title}' đã được gửi duyệt thành công.", job.id)
    db.commit()
    db.refresh(job)
    recalculate_all_skill_counts(db)
    return job


def withdraw_job_to_draft_service(db: Session, job_id: int, employer_id: int, expected_version: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin.")
    if job.employer_id != employer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền với tin này.")
    validate_job_transition(job.status, "draft", "employer")
    validate_optimistic_version(expected_version, job.version)
    old_st = job.status
    stmt = (
        update(Job).where(Job.id == job_id, Job.version == expected_version, Job.status == old_st)
        .values(status="draft", version=Job.version + 1)
    )
    if db.execute(stmt).rowcount == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VERSION_CONFLICT")
    db.add(JobStatusHistory(job_id=job.id, from_status=old_st, to_status="draft", changed_by=employer_id))
    db.commit()
    db.refresh(job)
    recalculate_all_skill_counts(db)
    return job


def approve_job_service(db: Session, job_id: int, admin_id: int, expected_version: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin.")
    validate_job_transition(job.status, "published", "admin")
    validate_optimistic_version(expected_version, job.version)
    old_st = job.status
    now_utc = datetime.now(timezone.utc)
    stmt = (
        update(Job).where(Job.id == job_id, Job.version == expected_version, Job.status == old_st)
        .values(status="published", version=Job.version + 1, reviewed_at=now_utc, published_at=now_utc)
    )
    if db.execute(stmt).rowcount == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VERSION_CONFLICT")
    db.add(JobStatusHistory(job_id=job.id, from_status=old_st, to_status="published", changed_by=admin_id))
    _send_moderation_notification(db, job.employer_id, "Tin tuyển dụng đã được phê duyệt", f"Tin tuyển dụng '{job.title}' của bạn đã được duyệt và hiển thị công khai.", job.id)
    db.commit()
    db.refresh(job)
    recalculate_all_skill_counts(db)
    return job


def reject_job_service(db: Session, job_id: int, admin_id: int, expected_version: int, reason: str) -> Job:
    clean_reason = validate_rejection_reason(reason)
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin.")
    validate_job_transition(job.status, "rejected", "admin")
    validate_optimistic_version(expected_version, job.version)
    old_st = job.status
    now_utc = datetime.now(timezone.utc)
    stmt = (
        update(Job).where(Job.id == job_id, Job.version == expected_version, Job.status == old_st)
        .values(status="rejected", version=Job.version + 1, review_note=clean_reason, reviewed_at=now_utc)
    )
    if db.execute(stmt).rowcount == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VERSION_CONFLICT")
    db.add(JobStatusHistory(job_id=job.id, from_status=old_st, to_status="rejected", changed_by=admin_id, reason=clean_reason))
    _send_moderation_notification(db, job.employer_id, "Tin tuyển dụng bị từ chối", f"Tin tuyển dụng '{job.title}' bị từ chối. Lý do: {clean_reason}", job.id)
    db.commit()
    db.refresh(job)
    recalculate_all_skill_counts(db)
    return job


def admin_delete_job_service(db: Session, job_id: int, admin_id: int, reason: str | None = None) -> Job:
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin.")
    clean_reason = (reason or "").strip()
    if job.status == "pending" and len(clean_reason) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vui lòng nhập lý do xóa tin chờ duyệt (tối thiểu 10 ký tự).",
        )
    old_st = job.status
    now_dt = datetime.now(timezone.utc)
    job.deleted_at = now_dt
    job.review_note = clean_reason or job.review_note
    job.version += 1
    db.add(JobStatusHistory(job_id=job.id, from_status=old_st, to_status="deleted", changed_by=admin_id, reason=clean_reason or "Admin xóa tin"))
    msg = f"Tin '{job.title}' đã bị ban quản trị xóa." + (f" Lý do: {clean_reason}" if clean_reason else "")
    _send_moderation_notification(db, job.employer_id, "Tin tuyển dụng đã bị xóa", msg, job.id)
    db.commit()
    db.refresh(job)
    recalculate_all_skill_counts(db)
    return job


def employer_delete_job_service(db: Session, job_id: int, employer_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng.")
    if job.employer_id != employer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền xóa tin của công ty khác.")
    job.deleted_at = datetime.now(timezone.utc)
    job.version += 1
    db.commit()
    db.refresh(job)
    recalculate_all_skill_counts(db)
    return job
