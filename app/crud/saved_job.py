from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Industry, Location
from app.models.company import Company
from app.models.job import Job
from app.models.saved_job import SavedJob


def save_job(db: Session, candidate_profile_id: int, job_id: int):
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
        raise


def get_saved_jobs(db: Session, candidate_profile_id: int):
    query = (
        select(
            SavedJob.id,
            Job.id.label("job_id"),
            Job.title,
            Company.name.label("company_name"),
            Industry.name.label("industry_name"),
            Location.name.label("location_name"),
            Job.deadline,
            SavedJob.saved_at,
        )
        .join(Job, SavedJob.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .join(Industry, Job.industry_id == Industry.id)
        .join(Location, Job.location_id == Location.id)
        .where(SavedJob.candidate_profile_id == candidate_profile_id)
        .order_by(SavedJob.saved_at.desc())
    )
    return db.execute(query).mappings().all()


def delete_saved_job(db: Session, candidate_profile_id: int, job_id: int):
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