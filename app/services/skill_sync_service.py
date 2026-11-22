"""Dịch vụ tự động đồng bộ danh mục kỹ năng và số lượng việc làm thật (< 100 dòng)."""
from collections import Counter
from datetime import date
import json

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaSkill


def sync_skills_from_job(db: Session, skills: list[str]) -> list[MetaSkill]:
    """Tự động thêm các kỹ năng mới vào meta_skills nếu chưa tồn tại."""
    if not skills:
        return []
    clean_skills = [s.strip() for s in skills if s and s.strip()]
    if not clean_skills:
        return []

    existing_rows = db.scalars(select(MetaSkill)).all()
    existing_map = {s.name.strip().lower(): s for s in existing_rows}
    created = []

    for name in clean_skills:
        lower_name = name.lower()
        if lower_name not in existing_map:
            new_skill = MetaSkill(name=name, usage_count=0)
            db.add(new_skill)
            existing_map[lower_name] = new_skill
            created.append(new_skill)

    if created:
        db.flush()
    return created


def recalculate_all_skill_counts(db: Session) -> dict[str, int]:
    """Quét toàn bộ tin tuyển dụng đang mở và cập nhật usage_count chuẩn xác cho meta_skills."""
    today = date.today()
    comp_ok = or_(
        Company.verification_status == "da_xac_minh",
        Company.status == CompanyStatus.VERIFIED,
        Company.is_verified == True,  # noqa: E712
    )
    stmt = (
        select(Job.skills)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(
            Job.status.in_(["open", "published"]),
            Job.deleted_at.is_(None),
            or_(Job.deadline.is_(None), Job.deadline >= today),
            or_(Job.company_id.is_(None), and_(comp_ok, Company.is_visible == True)),  # noqa: E712
        )
    )
    job_skills_rows = db.scalars(stmt).all()

    counts: Counter[str] = Counter()
    canonical_names: dict[str, str] = {}

    for raw in job_skills_rows:
        if not raw:
            continue
        items = raw if isinstance(raw, list) else []
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                items = parsed if isinstance(parsed, list) else [s.strip() for s in raw.split(",") if s.strip()]
            except Exception:
                items = [s.strip() for s in raw.split(",") if s.strip()]
        for s in items:
            name = str(s).strip()
            if name:
                key = name.lower()
                counts[key] += 1
                if key not in canonical_names:
                    canonical_names[key] = name

    existing_skills = db.scalars(select(MetaSkill)).all()
    existing_keys = set()
    result_map: dict[str, int] = {}

    for ms in existing_skills:
        key = ms.name.strip().lower()
        existing_keys.add(key)
        real_count = counts.get(key, 0)
        ms.usage_count = real_count
        result_map[ms.name] = real_count

    for key, real_count in counts.items():
        if key not in existing_keys:
            orig_name = canonical_names.get(key, key)
            db.add(MetaSkill(name=orig_name, usage_count=real_count))
            result_map[orig_name] = real_count

    db.commit()
    return result_map
