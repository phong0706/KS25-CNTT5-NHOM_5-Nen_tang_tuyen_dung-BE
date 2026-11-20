"""Router quản trị lương trung vị (/api/admin/home/salary-settings & /api/admin/home/skill-overrides).
Tuân thủ Bước 3 & techrecruit-rules: < 195 dòng.
"""
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job, MetaSkill
from app.models.home_config import HomeSalarySettings, HomeSalarySkillOverride
from app.models.user import User
from app.services.home_salary_service import calculate_median_salary, filter_eligible_salary_jobs, SalarySettingsPayload
from app.services.home_config_service import invalidate_home_cache, record_audit

router = APIRouter(prefix="/admin/home", tags=["Admin Home Salary Settings"])


class SkillOverrideIn(BaseModel):
    skill_id: int
    skill_name: Optional[str] = None
    mode: str = Field(..., pattern="^(pinned|hidden|auto)$")
    position: Optional[int] = Field(None, ge=1, le=12)


class UpdateSkillOverridesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    reason: str
    overrides: List[SkillOverrideIn]

    @field_validator("reason")
    @classmethod
    def check_reason(cls, v: str) -> str:
        s = v.strip() if isinstance(v, str) else ""
        if len(s) < 10:
            raise ValueError("Lý do bắt buộc tối thiểu 10 ký tự.")
        return s


class UpdateSalarySettingsIn(SalarySettingsPayload):
    model_config = ConfigDict(extra="forbid")


@router.get("/salary-settings")
def get_admin_salary_settings(db: Session = Depends(get_db), admin: User = Depends(role_required("admin"))):
    s = db.scalar(select(HomeSalarySettings).where(HomeSalarySettings.id == 1))
    if not s:
        s = HomeSalarySettings(id=1, min_sample=5, max_items=6, version=1)
        db.add(s)
        db.commit()

    ov_rows = db.execute(select(HomeSalarySkillOverride)).scalars().all()
    ov_map = {o.skill_id: o for o in ov_rows}

    today = date.today()
    stmt = (
        select(Job.skills, Job.salary_min, Job.salary_max, Job.status, Job.deleted_at,
               Job.is_salary_negotiable, Job.deadline, Company.is_verified, Company.verification_status)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Job.status == "published", Job.deleted_at.is_(None), Job.is_salary_negotiable == False)
    )
    raw_jobs = [
        {"skills": r.skills, "salary_min": r.salary_min, "salary_max": r.salary_max, "status": r.status,
         "deleted_at": r.deleted_at, "is_salary_negotiable": r.is_salary_negotiable, "deadline": r.deadline,
         "is_company_verified": bool(r.is_verified or r.verification_status == "da_xac_minh")}
        for r in db.execute(stmt).all()
    ]
    eligible = filter_eligible_salary_jobs(raw_jobs, now_date=today)

    sk_salaries = defaultdict(list)
    for j in eligible:
        sal = j["computed_salary"]
        for sk in (j.get("skills") or []):
            name = (sk.get("name", "") if isinstance(sk, dict) else str(sk)).strip()
            if name:
                sk_salaries[name].append(sal)

    db_skills = db.execute(select(MetaSkill)).scalars().all()
    skill_dict = {s_obj.name.lower(): s_obj for s_obj in db_skills}

    skills_out = []
    for name, sals in sk_salaries.items():
        obj = skill_dict.get(name.lower())
        sk_id = obj.id if obj else hash(name) % 100000 + 10000
        ov = ov_map.get(sk_id)
        med = calculate_median_salary(sals)
        skills_out.append({
            "skill_id": sk_id,
            "skill_name": name,
            "sample_count": len(sals),
            "median_salary": med,
            "mode": ov.mode if ov else "auto",
            "position": ov.position if ov else None,
        })

    skills_out.sort(key=lambda x: (-(x["position"] or 999) if x["mode"] == "pinned" else 0, -x["median_salary"], x["skill_name"]))
    return {
        "min_sample": s.min_sample,
        "max_items": s.max_items,
        "version": s.version,
        "updated_by": s.updated_by,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "skills": skills_out,
    }


@router.put("/salary-settings")
def update_admin_salary_settings(payload: UpdateSalarySettingsIn, db: Session = Depends(get_db), admin: User = Depends(role_required("admin"))):
    s = db.scalar(select(HomeSalarySettings).where(HomeSalarySettings.id == 1))
    if not s:
        s = HomeSalarySettings(id=1, min_sample=5, max_items=6, version=1)
        db.add(s)
        db.commit()

    if s.version != payload.version:
        raise HTTPException(status_code=409, detail="Cấu hình đã được người khác thay đổi. Tải lại để xem bản mới nhất.")

    before = {"min_sample": s.min_sample, "max_items": s.max_items, "version": s.version}
    res = db.execute(
        update(HomeSalarySettings)
        .where(HomeSalarySettings.id == 1, HomeSalarySettings.version == payload.version)
        .values(min_sample=payload.min_sample, max_items=payload.max_items, version=payload.version + 1, updated_by=admin.id)
    )
    if res.rowcount == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cấu hình đã được người khác thay đổi. Tải lại để xem bản mới nhất.")

    after = {"min_sample": payload.min_sample, "max_items": payload.max_items, "version": payload.version + 1}
    record_audit(db, "salary", "update_settings", admin.id, before, after, payload.reason)
    db.commit()
    invalidate_home_cache()
    return {"message": "Cập nhật thành công", "version": payload.version + 1, "min_sample": payload.min_sample, "max_items": payload.max_items}


@router.put("/skill-overrides")
def update_admin_skill_overrides(payload: UpdateSkillOverridesIn, db: Session = Depends(get_db), admin: User = Depends(role_required("admin"))):
    s = db.scalar(select(HomeSalarySettings).where(HomeSalarySettings.id == 1))
    if s and s.version != payload.version:
        raise HTTPException(status_code=409, detail="Cấu hình đã được người khác thay đổi. Tải lại để xem bản mới nhất.")

    pinned_count = sum(1 for o in payload.overrides if o.mode == "pinned")
    max_items = s.max_items if s else 6
    if pinned_count > max_items:
        raise HTTPException(status_code=422, detail=f"Không được ghim quá {max_items} kỹ năng.")

    valid_skill_ids = set(db.execute(select(MetaSkill.id)).scalars().all())
    for o in payload.overrides:
        if o.skill_id not in valid_skill_ids:
            raise HTTPException(status_code=422, detail=f"Kỹ năng id {o.skill_id} không tồn tại trong hệ thống.")

    before_rows = db.execute(select(HomeSalarySkillOverride)).scalars().all()
    before = [{"skill_id": r.skill_id, "mode": r.mode, "position": r.position} for r in before_rows]

    res = db.execute(
        update(HomeSalarySettings)
        .where(HomeSalarySettings.id == 1, HomeSalarySettings.version == payload.version)
        .values(version=payload.version + 1, updated_by=admin.id)
    )
    if res.rowcount == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cấu hình đã được người khác thay đổi. Tải lại để xem bản mới nhất.")

    for o in payload.overrides:
        existing = db.scalar(select(HomeSalarySkillOverride).where(HomeSalarySkillOverride.skill_id == o.skill_id))
        if existing:
            existing.mode = o.mode
            existing.position = o.position
            existing.updated_by = admin.id
        else:
            db.add(HomeSalarySkillOverride(
                skill_id=o.skill_id,
                skill_name=o.skill_name or f"Skill {o.skill_id}",
                mode=o.mode,
                position=o.position,
                updated_by=admin.id,
            ))

    after = [{"skill_id": o.skill_id, "mode": o.mode, "position": o.position} for o in payload.overrides]
    record_audit(db, "salary", "update_skills", admin.id, before, after, payload.reason)
    db.commit()
    invalidate_home_cache()
    return {"message": "Cập nhật ghim/ẩn kỹ năng thành công", "version": payload.version + 1}
