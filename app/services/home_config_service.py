"""Dịch vụ nghiệp vụ cấu hình trang chủ, bộ nhớ đệm 60s, kiểm tra phiên bản & nhật ký audit.
Tuân thủ Bước 1, Bước 2 & techrecruit-rules: < 195 dòng, transaction an toàn.
"""
from datetime import datetime, date, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.company import Company
from app.models.job import Job
from app.models.home_config import (
    HomeSalarySettings,
    HomeSalarySkillOverride,
    HomeFeaturedCompany,
    HomeConfigAudit,
)
from app.services.home_salary_service import (
    filter_eligible_salary_jobs,
    aggregate_skills_salary,
)

# In-memory cache với computed_at & cờ is_dirty
_CACHE = {
    "salary": {"data": None, "computed_at": None, "is_dirty": True},
    "companies": {"data": None, "computed_at": None, "is_dirty": True},
}


def invalidate_home_cache():
    _CACHE["salary"]["is_dirty"] = True
    _CACHE["companies"]["is_dirty"] = True


def get_public_salary_by_skill(db: Session) -> Dict[str, Any]:
    now = datetime.now()
    c = _CACHE["salary"]
    if not c["is_dirty"] and c["data"] and c["computed_at"]:
        if (now - c["computed_at"]).total_seconds() < 60:
            return c["data"]

    # 1. Lấy settings hiện tại
    settings = db.scalar(select(HomeSalarySettings).where(HomeSalarySettings.id == 1))
    min_sample = settings.min_sample if settings else 5
    max_items = settings.max_items if settings else 6

    # 2. Lấy overrides
    overrides_rows = db.execute(select(HomeSalarySkillOverride)).scalars().all()
    overrides_map = {ov.skill_name: {"mode": ov.mode, "position": ov.position} for ov in overrides_rows}

    # 3. Lấy tin tuyển dụng thô
    today = date.today()
    stmt = (
        select(Job.skills, Job.salary_min, Job.salary_max, Job.status, Job.deleted_at,
               Job.is_salary_negotiable, Job.deadline, Company.is_verified, Company.verification_status)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Job.status == "published", Job.deleted_at.is_(None), Job.is_salary_negotiable == False)
    )
    rows = db.execute(stmt).all()

    raw_jobs = []
    for r in rows:
        is_ver = bool(r.is_verified or r.verification_status == "da_xac_minh")
        raw_jobs.append({
            "skills": r.skills,
            "salary_min": r.salary_min,
            "salary_max": r.salary_max,
            "status": r.status,
            "deleted_at": r.deleted_at,
            "is_salary_negotiable": r.is_salary_negotiable,
            "deadline": r.deadline,
            "is_company_verified": is_ver,
        })

    eligible = filter_eligible_salary_jobs(raw_jobs, now_date=today)
    aggregated = aggregate_skills_salary(eligible, min_sample=min_sample, max_items=max_items, overrides=overrides_map)

    items = [
        {"skill": a["skill"], "median": a["median_salary"], "unit": "tr/tháng", "sample_size": a["sample_count"]}
        for a in aggregated
    ]
    reason = None if items else f"Chưa có kỹ năng nào đủ {min_sample} tin có lương công khai. Hạ ngưỡng hoặc chờ thêm tin tuyển dụng."

    result = {
        "computed_at": now.isoformat(),
        "min_sample": min_sample,
        "items": items,
        "reason": reason,
    }
    c["data"] = result
    c["computed_at"] = now
    c["is_dirty"] = False
    return result


def get_public_featured_companies(db: Session) -> Dict[str, Any]:
    now = datetime.now()
    c = _CACHE["companies"]
    if not c["is_dirty"] and c["data"] and c["computed_at"]:
        if (now - c["computed_at"]).total_seconds() < 60:
            return c["data"]

    today = date.today()
    # Công ty đã xác minh, có ít nhất 1 tin published còn hạn
    subq = (
        select(Job.company_id, func.count(Job.id).label("open_jobs"))
        .where(
            Job.status == "published",
            Job.deleted_at.is_(None),
            (Job.deadline.is_(None) | (Job.deadline >= today))
        )
        .group_by(Job.company_id)
        .subquery()
    )

    stmt = (
        select(Company.id, Company.name, Company.logo_url, Company.logo_status, subq.c.open_jobs, HomeFeaturedCompany.position)
        .join(subq, Company.id == subq.c.company_id)
        .outerjoin(HomeFeaturedCompany, Company.id == HomeFeaturedCompany.company_id)
        .where(
            (Company.is_verified == True) | (Company.verification_status == "da_xac_minh"),
            Company.is_visible == True,
            Company.is_draft == False,
        )
    )
    rows = db.execute(stmt).all()

    pinned, auto = [], []
    for r in rows:
        cid, name, logo, l_status, open_j, pos = r
        actual_logo = logo if (logo and l_status != "removed") else None
        info = {"company_id": cid, "name": name, "logo_url": actual_logo, "open_jobs": int(open_j or 0), "position": pos}
        if pos is not None:
            pinned.append(info)
        else:
            auto.append(info)

    pinned.sort(key=lambda x: (x["position"], -x["open_jobs"], x["name"]))
    auto.sort(key=lambda x: (-x["open_jobs"], x["name"]))
    items = (pinned + auto)[:12]

    result = {"computed_at": now.isoformat(), "items": items}
    c["data"] = result
    c["computed_at"] = now
    c["is_dirty"] = False
    return result


def record_audit(db: Session, section: str, action: str, actor_id: int, before_val: Any, after_val: Any, reason: str):
    audit = HomeConfigAudit(
        section=section,
        action=action,
        actor_id=actor_id,
        before_json=json.dumps(before_val, ensure_ascii=False) if before_val is not None else None,
        after_json=json.dumps(after_val, ensure_ascii=False) if after_val is not None else None,
        reason=reason.strip(),
    )
    db.add(audit)
