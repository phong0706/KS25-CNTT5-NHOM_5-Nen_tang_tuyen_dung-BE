from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Industry, Location, Skill
from app.models.company import Company
from app.models.job import Job
from app.models.job_skill import JobSkill


def search_jobs(
    db: Session,
    keyword: str | None = None,
    industry_id: int | None = None,
    location_id: int | None = None,
    skill_id: int | None = None,
):
    query = (
        select(
            Job.id,
            Job.title,
            Job.description,
            Company.name.label("company_name"),
            Industry.name.label("industry_name"),
            Location.name.label("location_name"),
            Job.deadline,
            Job.created_at,
        )
        .join(Company, Job.company_id == Company.id)
        .join(Industry, Job.industry_id == Industry.id)
        .join(Location, Job.location_id == Location.id)
        .outerjoin(JobSkill, JobSkill.job_id == Job.id)
        .outerjoin(Skill, Skill.id == JobSkill.skill_id)
        .where(Job.status == "OPEN", Job.deadline >= func.now())
        .distinct()
    )

    if keyword:
        query = query.where(Job.title.ilike(f"%{keyword}%"))
    if industry_id is not None:
        query = query.where(Job.industry_id == industry_id)
    if location_id is not None:
        query = query.where(Job.location_id == location_id)
    if skill_id is not None:
        query = query.where(Skill.id == skill_id)

    query = query.order_by(Job.created_at.desc())
    return db.execute(query).mappings().all()