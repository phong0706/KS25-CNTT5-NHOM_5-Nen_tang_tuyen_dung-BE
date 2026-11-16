"""CRUD operations cho tính năng Lưu tin tuyển dụng (SavedJob)."""
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate import CandidateProfile
from app.models.catalog import Industry, Location
from app.models.company import Company
from app.models.job import Job
from app.models.saved_job import SavedJob


def save_job(db: Session, candidate_profile_id: int, job_id: int) -> SavedJob:
    """Lưu tin tuyển dụng vào danh sách yêu thích của ứng viên.

    Kiểm tra:
    - Hồ sơ ứng viên tồn tại
    - Tin tuyển dụng tồn tại, đang ở trạng thái OPEN và còn hạn nộp
    - Không lưu trùng (UNIQUE constraint: candidate_profile_id + job_id)
    """
    profile = db.get(CandidateProfile, candidate_profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ ứng viên id={candidate_profile_id}",
        )

    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tin tuyển dụng id={job_id}",
        )

    if job.status != "OPEN" or (job.deadline and job.deadline < datetime.now()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể lưu tin tuyển dụng đang mở (OPEN) và còn hạn nộp hồ sơ",
        )

    existing = db.scalar(
        select(SavedJob).where(
            SavedJob.candidate_profile_id == candidate_profile_id,
            SavedJob.job_id == job_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tin tuyển dụng này đã có trong danh sách lưu của bạn",
        )

    saved_job = SavedJob(
        candidate_profile_id=candidate_profile_id,
        job_id=job_id,
    )
    db.add(saved_job)
    try:
        db.commit()
        db.refresh(saved_job)
        return saved_job
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tin tuyển dụng đã được lưu hoặc dữ liệu không hợp lệ",
        )


def get_saved_jobs(db: Session, candidate_profile_id: int) -> list[dict]:
    """Lấy danh sách các tin tuyển dụng đã lưu của ứng viên (kèm thông tin công ty, ngành, địa điểm)."""
    query = (
        select(
            SavedJob.id,
            Job.id.label("job_id"),
            Job.title,
            Company.id.label("company_id"),
            Company.name.label("company_name"),
            Company.logo.label("company_logo"),
            Industry.id.label("industry_id"),
            Industry.name.label("industry_name"),
            Location.id.label("location_id"),
            Location.name.label("location_name"),
            Job.job_type,
            Job.experience_level,
            Job.salary_min,
            Job.salary_max,
            Job.is_negotiable,
            Job.currency,
            Job.deadline,
            SavedJob.saved_at,
        )
        .join(Job, SavedJob.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .join(Industry, Job.industry_id == Industry.id)
        .join(Location, Job.location_id == Location.id)
        .where(SavedJob.candidate_profile_id == candidate_profile_id)
        .order_by(SavedJob.saved_at.desc(), SavedJob.id.desc())
    )
    return [dict(row) for row in db.execute(query).mappings().all()]


def delete_saved_job(db: Session, candidate_profile_id: int, job_id: int) -> bool:
    """Bỏ lưu 1 tin tuyển dụng của ứng viên."""
    saved_job = db.scalar(
        select(SavedJob).where(
            SavedJob.candidate_profile_id == candidate_profile_id,
            SavedJob.job_id == job_id,
        )
    )
    if saved_job is None:
        return False
    db.delete(saved_job)
    db.commit()
    return True


def is_job_saved(db: Session, candidate_profile_id: int, job_id: int) -> bool:
    """Kiểm tra ứng viên đã lưu tin tuyển dụng này chưa."""
    saved_id = db.scalar(
        select(SavedJob.id).where(
            SavedJob.candidate_profile_id == candidate_profile_id,
            SavedJob.job_id == job_id,
        )
    )
    return saved_id is not None


def get_saved_job_ids(
    db: Session, candidate_profile_id: int, job_ids: list[int]
) -> set[int]:
    """Lấy tập hợp các job_id đã được ứng viên lưu trong danh sách job_ids."""
    if not job_ids:
        return set()
    rows = db.scalars(
        select(SavedJob.job_id).where(
            SavedJob.candidate_profile_id == candidate_profile_id,
            SavedJob.job_id.in_(job_ids),
        )
    ).all()
    return set(rows)