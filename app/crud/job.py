from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.catalog import Industry, Location, Skill
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.job_skill import JobSkill
from app.schemas.job import JobCreate, JobUpdate


def _company_for_employer(db: Session, employer_id: int) -> Company:
    company = db.scalar(select(Company).where(Company.employer_id == employer_id))
    if company is None or company.status != CompanyStatus.VERIFIED:
        raise HTTPException(status_code=403, detail="Công ty chưa được xác minh hoặc không tồn tại")
    return company


def _owned_job(db: Session, job_id: int, user_id: int, *, is_admin: bool = False) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin tuyển dụng")
    if is_admin:
        return job
    company = _company_for_employer(db, user_id)
    if job.company_id != company.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên tin tuyển dụng của công ty khác")
    return job


def _validate_references(db: Session, industry_id: int, location_id: int, skills) -> list:
    if db.get(Industry, industry_id) is None:
        raise HTTPException(status_code=400, detail="industry_id không tồn tại")
    if db.get(Location, location_id) is None:
        raise HTTPException(status_code=400, detail="location_id không tồn tại")
    unique_skills = {}
    for item in skills or []:
        skill_id = item.skill_id
        if db.get(Skill, skill_id) is None:
            raise HTTPException(status_code=400, detail=f"skill_id {skill_id} không tồn tại")
        unique_skills[skill_id] = item
    return list(unique_skills.values())


def _validate_salary(is_negotiable: bool, salary_min, salary_max) -> None:
    if is_negotiable:
        if salary_min is not None or salary_max is not None:
            raise HTTPException(status_code=400, detail="Lương thỏa thuận phải để salary_min và salary_max là null")
        return
    if salary_min is None or salary_max is None or salary_min <= 0 or salary_max <= 0:
        raise HTTPException(status_code=400, detail="salary_min và salary_max phải lớn hơn 0 khi không chọn lương thỏa thuận")
    if salary_min > salary_max:
        raise HTTPException(status_code=400, detail="Mức lương tối thiểu không được lớn hơn mức lương tối đa")


def _validate_deadline(deadline: datetime) -> datetime:
    value = deadline.replace(tzinfo=timezone.utc) if deadline.tzinfo is None else deadline
    if value <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Hạn nộp hồ sơ phải là một thời điểm trong tương lai")
    # The database columns use timezone-naive DATETIME and store UTC.
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _replace_skills(db: Session, job_id: int, skills) -> None:
    db.execute(delete(JobSkill).where(JobSkill.job_id == job_id))
    for item in skills:
        db.add(JobSkill(job_id=job_id, skill_id=item.skill_id, is_required=item.is_required))


def _job_detail(db: Session, job: Job) -> dict:
    result = {column.name: getattr(job, column.name) for column in Job.__table__.columns}
    result["job_skills"] = db.scalars(select(JobSkill).where(JobSkill.job_id == job.id)).all()
    return result


def create_job(db: Session, user_id: int, data: JobCreate, *, is_admin: bool = False) -> dict:
    if is_admin:
        if data.company_id is None:
            raise HTTPException(status_code=400, detail="ADMIN phải truyền company_id khi đăng tin thay mặt công ty")
        company = db.get(Company, data.company_id)
        if company is None or company.status != CompanyStatus.VERIFIED:
            raise HTTPException(status_code=403, detail="Công ty chưa được xác minh hoặc không tồn tại")
    else:
        if data.company_id is not None:
            raise HTTPException(status_code=403, detail="Nhà tuyển dụng không được tự chọn company_id")
        company = _company_for_employer(db, user_id)
    skills = _validate_references(db, data.industry_id, data.location_id, data.skills)
    _validate_salary(data.is_negotiable, data.salary_min, data.salary_max)
    values = data.model_dump(exclude={"skills", "deadline", "company_id"})
    job = Job(
        **values,
        deadline=_validate_deadline(data.deadline),
        company_id=company.id,
        posted_by=user_id,
    )
    try:
        db.add(job)
        db.flush()
        _replace_skills(db, job.id, skills)
        db.commit()
        db.refresh(job)
    except Exception:
        db.rollback()
        raise
    return _job_detail(db, job)


def update_job(db: Session, job_id: int, user_id: int, data: JobUpdate) -> dict:
    job = _owned_job(db, job_id, user_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Cần truyền ít nhất một trường để cập nhật")
    for field in ("title", "industry_id", "location_id", "job_type", "experience_level", "quantity", "description", "deadline"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=400, detail=f"{field} không được để trống")
    if "title" in changes and not changes["title"].strip():
        raise HTTPException(status_code=400, detail="title không được để trống")
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    skills = changes.pop("skills", None)
    merged = {key: changes.get(key, getattr(job, key)) for key in (
        "industry_id", "location_id", "is_negotiable", "salary_min", "salary_max", "deadline"
    )}
    _validate_salary(merged["is_negotiable"], merged["salary_min"], merged["salary_max"])
    deadline = _validate_deadline(merged["deadline"])
    _validate_references(db, merged["industry_id"], merged["location_id"], skills or [])
    for field, value in changes.items():
        setattr(job, field, deadline if field == "deadline" else value)
    if "deadline" not in changes:
        job.deadline = deadline
    if skills is not None:
        _replace_skills(db, job.id, _validate_references(db, job.industry_id, job.location_id, skills))
    db.commit()
    db.refresh(job)
    return _job_detail(db, job)


def change_job_status(db: Session, job_id: int, user_id: int, new_status: str, *, is_admin: bool = False) -> dict:
    job = _owned_job(db, job_id, user_id, is_admin=is_admin)
    if not is_admin and new_status == "OPEN":
        company = _company_for_employer(db, user_id)
        if company.id != job.company_id:
            raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên tin tuyển dụng của công ty khác")
    job.status = new_status
    db.commit()
    db.refresh(job)
    return _job_detail(db, job)


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
