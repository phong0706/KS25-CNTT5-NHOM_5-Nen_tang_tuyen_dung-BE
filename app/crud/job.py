"""CRUD operations cho Tin tuyển dụng (Job): đăng tin, sửa tin, đổi trạng thái và tìm kiếm nâng cao."""
from datetime import datetime, timezone
from decimal import Decimal
import math

from fastapi import HTTPException
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.orm import Session

from app.crud.saved_job import get_saved_job_ids
from app.models.catalog import Industry, Location, Skill
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.job_skill import JobSkill
from app.schemas.job import JobCreate, JobUpdate


def _company_for_employer(db: Session, employer_id: int) -> Company:
    company = db.scalar(select(Company).where(Company.employer_id == employer_id))
    if company is None or company.status != CompanyStatus.VERIFIED:
        raise HTTPException(
            status_code=403, detail="Công ty chưa được xác minh hoặc không tồn tại"
        )
    return company


def _owned_job(
    db: Session, job_id: int, user_id: int, *, is_admin: bool = False
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin tuyển dụng")
    if is_admin:
        return job
    company = _company_for_employer(db, user_id)
    if job.company_id != company.id:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền thao tác trên tin tuyển dụng của công ty khác",
        )
    return job


def _validate_references(
    db: Session, industry_id: int, location_id: int, skills
) -> list:
    if db.get(Industry, industry_id) is None:
        raise HTTPException(status_code=400, detail="industry_id không tồn tại")
    if db.get(Location, location_id) is None:
        raise HTTPException(status_code=400, detail="location_id không tồn tại")
    unique_skills = {}
    for item in skills or []:
        skill_id = item.skill_id
        if db.get(Skill, skill_id) is None:
            raise HTTPException(
                status_code=400, detail=f"skill_id {skill_id} không tồn tại"
            )
        unique_skills[skill_id] = item
    return list(unique_skills.values())


def _validate_salary(is_negotiable: bool, salary_min, salary_max) -> None:
    if is_negotiable:
        if salary_min is not None or salary_max is not None:
            raise HTTPException(
                status_code=400,
                detail="Lương thỏa thuận phải để salary_min và salary_max là null",
            )
        return
    if salary_min is None or salary_max is None or salary_min <= 0 or salary_max <= 0:
        raise HTTPException(
            status_code=400,
            detail="salary_min và salary_max phải lớn hơn 0 khi không chọn lương thỏa thuận",
        )
    if salary_min > salary_max:
        raise HTTPException(
            status_code=400,
            detail="Mức lương tối thiểu không được lớn hơn mức lương tối đa",
        )


def _validate_deadline(deadline: datetime) -> datetime:
    value = (
        deadline.replace(tzinfo=timezone.utc)
        if deadline.tzinfo is None
        else deadline
    )
    if value <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Hạn nộp hồ sơ phải là một thời điểm trong tương lai",
        )
    # Database sử dụng DATETIME (naive UTC)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _replace_skills(db: Session, job_id: int, skills) -> None:
    db.execute(delete(JobSkill).where(JobSkill.job_id == job_id))
    for item in skills:
        db.add(
            JobSkill(
                job_id=job_id,
                skill_id=item.skill_id,
                is_required=item.is_required,
            )
        )


def _job_detail(db: Session, job: Job) -> dict:
    result = {
        column.name: getattr(job, column.name) for column in Job.__table__.columns
    }
    result["job_skills"] = list(
        db.scalars(select(JobSkill).where(JobSkill.job_id == job.id)).all()
    )
    return result


def get_job_by_id(db: Session, job_id: int) -> dict | None:
    """Lấy chi tiết 1 tin tuyển dụng theo ID (kèm danh sách kỹ năng)."""
    job = db.get(Job, job_id)
    if job is None:
        return None
    return _job_detail(db, job)


def create_job(
    db: Session, user_id: int, data: JobCreate, *, is_admin: bool = False
) -> dict:
    if is_admin:
        if data.company_id is None:
            raise HTTPException(
                status_code=400,
                detail="ADMIN phải truyền company_id khi đăng tin thay mặt công ty",
            )
        company = db.get(Company, data.company_id)
        if company is None or company.status != CompanyStatus.VERIFIED:
            raise HTTPException(
                status_code=403,
                detail="Công ty chưa được xác minh hoặc không tồn tại",
            )
    else:
        if data.company_id is not None:
            raise HTTPException(
                status_code=403,
                detail="Nhà tuyển dụng không được tự chọn company_id",
            )
        company = _company_for_employer(db, user_id)
    skills = _validate_references(
        db, data.industry_id, data.location_id, data.skills
    )
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
        raise HTTPException(
            status_code=400, detail="Cần truyền ít nhất một trường để cập nhật"
        )
    for field in (
        "title",
        "industry_id",
        "location_id",
        "job_type",
        "experience_level",
        "quantity",
        "description",
        "deadline",
    ):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=400, detail=f"{field} không được để trống"
            )
    if "title" in changes and not changes["title"].strip():
        raise HTTPException(status_code=400, detail="title không được để trống")
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    skills = changes.pop("skills", None)
    merged = {
        key: changes.get(key, getattr(job, key))
        for key in (
            "industry_id",
            "location_id",
            "is_negotiable",
            "salary_min",
            "salary_max",
            "deadline",
        )
    }
    _validate_salary(
        merged["is_negotiable"], merged["salary_min"], merged["salary_max"]
    )
    deadline = _validate_deadline(merged["deadline"])
    _validate_references(
        db, merged["industry_id"], merged["location_id"], skills or []
    )
    for field, value in changes.items():
        setattr(job, field, deadline if field == "deadline" else value)
    if "deadline" not in changes:
        job.deadline = deadline
    if skills is not None:
        _replace_skills(
            db,
            job.id,
            _validate_references(db, job.industry_id, job.location_id, skills),
        )
    db.commit()
    db.refresh(job)
    return _job_detail(db, job)


def change_job_status(
    db: Session,
    job_id: int,
    user_id: int,
    new_status: str,
    *,
    is_admin: bool = False,
) -> dict:
    job = _owned_job(db, job_id, user_id, is_admin=is_admin)
    if not is_admin and new_status == "OPEN":
        company = _company_for_employer(db, user_id)
        if company.id != job.company_id:
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền thao tác trên tin tuyển dụng của công ty khác",
            )
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
    salary_min: Decimal | float | None = None,
    salary_max: Decimal | float | None = None,
    job_type: str | None = None,
    experience_level: str | None = None,
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 10,
    candidate_profile_id: int | None = None,
) -> dict:
    """Tìm kiếm và lọc tin tuyển dụng nâng cao có phân trang.

    Đặc điểm truy vấn:
    - JOIN bảng companies, industries, locations và OUTER JOIN job_skills, skills
    - Chỉ lấy các tin tuyển dụng có status = 'OPEN' và còn hạn nộp (deadline >= hiện tại)
    - Tìm theo từ khóa (keyword) trên cả 3 trường: tiêu đề tin, tên công ty, tên kỹ năng
    - Lọc theo: ngành nghề (industry_id), địa điểm (location_id), kỹ năng (skill_id),
      khoảng lương (salary_min, salary_max), hình thức làm việc (job_type), kinh nghiệm (experience_level)
    - Sắp xếp: 'newest' (mới nhất trước) hoặc 'salary_desc' (lương cao nhất trước) / 'salary_asc'
    - Phân trang: trả về items, total, page, page_size, total_pages
    - Nếu người dùng là ứng viên đã đăng nhập (có candidate_profile_id), trả thêm cờ is_saved cho từng tin.
    """
    now = datetime.now()

    # Điều kiện cơ bản: chỉ lấy tin OPEN và còn hạn nộp hồ sơ
    conditions = [
        Job.status == "OPEN",
        Job.deadline >= now,
    ]

    # 1. Tìm kiếm theo từ khóa (tiêu đề, tên công ty, hoặc tên kỹ năng)
    if keyword and keyword.strip():
        kw_pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(
                Job.title.ilike(kw_pattern),
                Company.name.ilike(kw_pattern),
                Skill.name.ilike(kw_pattern),
            )
        )

    # 2. Lọc theo ngành nghề, địa điểm, kỹ năng
    if industry_id is not None:
        conditions.append(Job.industry_id == industry_id)
    if location_id is not None:
        conditions.append(Job.location_id == location_id)
    if skill_id is not None:
        conditions.append(JobSkill.skill_id == skill_id)

    # 3. Lọc theo khoảng lương (overlap giữa khoảng lương của tin và khoảng lọc)
    if salary_min is not None:
        conditions.append(
            func.coalesce(Job.salary_max, Job.salary_min) >= salary_min
        )
    if salary_max is not None:
        conditions.append(
            func.coalesce(Job.salary_min, Job.salary_max) <= salary_max
        )

    # 4. Lọc theo hình thức làm việc (FULLTIME, PARTTIME, INTERN, REMOTE)
    if job_type and job_type.strip():
        conditions.append(func.upper(Job.job_type) == job_type.strip().upper())

    # 5. Lọc theo kinh nghiệm (khớp chuỗi con không phân biệt hoa thường)
    if experience_level and experience_level.strip():
        conditions.append(
            Job.experience_level.ilike(f"%{experience_level.strip()}%")
        )

    # Đếm tổng số tin tuyển dụng thỏa mãn bộ lọc (loại trùng do JOIN 1-N với job_skills)
    count_query = (
        select(func.count(func.distinct(Job.id)))
        .select_from(Job)
        .join(Company, Job.company_id == Company.id)
        .join(Industry, Job.industry_id == Industry.id)
        .join(Location, Job.location_id == Location.id)
        .outerjoin(JobSkill, JobSkill.job_id == Job.id)
        .outerjoin(Skill, Skill.id == JobSkill.skill_id)
        .where(*conditions)
    )
    total: int = db.scalar(count_query) or 0

    # Câu truy vấn chính lấy thông tin tin tuyển dụng kèm công ty, ngành, địa điểm
    base_query = (
        select(
            Job.id,
            Job.title,
            Job.description,
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
            Job.created_at,
        )
        .join(Company, Job.company_id == Company.id)
        .join(Industry, Job.industry_id == Industry.id)
        .join(Location, Job.location_id == Location.id)
        .outerjoin(JobSkill, JobSkill.job_id == Job.id)
        .outerjoin(Skill, Skill.id == JobSkill.skill_id)
        .where(*conditions)
        .group_by(
            Job.id,
            Company.id,
            Company.name,
            Company.logo,
            Industry.id,
            Industry.name,
            Location.id,
            Location.name,
        )
    )

    # 6. Sắp xếp kết quả
    has_concrete_salary = case(
        (and_(Job.salary_max.is_(None), Job.salary_min.is_(None)), 0),
        else_=1,
    )
    effective_max_salary = func.coalesce(Job.salary_max, Job.salary_min, 0)
    effective_min_salary = func.coalesce(Job.salary_min, Job.salary_max, 0)

    normalized_sort = (sort_by or "newest").strip().lower()
    if normalized_sort in {"salary_desc", "salary_high", "salary"}:
        base_query = base_query.order_by(
            has_concrete_salary.desc(),
            effective_max_salary.desc(),
            effective_min_salary.desc(),
            Job.created_at.desc(),
            Job.id.desc(),
        )
    elif normalized_sort in {"salary_asc", "salary_low"}:
        base_query = base_query.order_by(
            has_concrete_salary.desc(),
            effective_min_salary.asc(),
            effective_max_salary.asc(),
            Job.created_at.desc(),
            Job.id.desc(),
        )
    else:
        # Mặc định: sắp xếp mới nhất trước
        base_query = base_query.order_by(Job.created_at.desc(), Job.id.desc())

    # 7. Phân trang
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    rows = db.execute(base_query.offset(offset).limit(page_size)).mappings().all()
    items = [dict(row) for row in rows]

    # 8. Bổ sung danh sách tên kỹ năng và trạng thái đã lưu (is_saved) cho các tin trong trang hiện tại
    job_ids = [item["id"] for item in items]
    skills_by_job: dict[int, list[str]] = {jid: [] for jid in job_ids}
    if job_ids:
        skill_rows = db.execute(
            select(JobSkill.job_id, Skill.name)
            .join(Skill, Skill.id == JobSkill.skill_id)
            .where(JobSkill.job_id.in_(job_ids))
            .order_by(JobSkill.is_required.desc(), Skill.name.asc())
        ).all()
        for jid, sname in skill_rows:
            if sname not in skills_by_job.get(jid, []):
                skills_by_job.setdefault(jid, []).append(sname)

    saved_ids: set[int] = set()
    if candidate_profile_id is not None and job_ids:
        saved_ids = get_saved_job_ids(db, candidate_profile_id, job_ids)

    for item in items:
        jid = item["id"]
        item["skills"] = skills_by_job.get(jid, [])
        item["is_saved"] = jid in saved_ids

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
