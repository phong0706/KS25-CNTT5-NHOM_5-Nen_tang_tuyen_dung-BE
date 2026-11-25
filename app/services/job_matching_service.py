"""Dịch vụ tính toán & đồng bộ điểm phù hợp việc làm (Matching Service).
Tuân thủ techrecruit-rules: <= 200 dòng.
"""
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job, JobApplication
from app.models.match_score import CandidateMatchingSetting, MatchScore, SkillJobIndex
from app.services.pure_job_matching import DEFAULT_CONFIG, compute_pure_match, normalize_skill_name


def get_or_create_candidate_settings(db: Session, user_id: int) -> CandidateMatchingSetting:
    setting = db.query(CandidateMatchingSetting).filter_by(user_id=user_id).first()
    if not setting:
        setting = CandidateMatchingSetting(user_id=user_id, is_enabled=True, open_to_relocate=False)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def sync_skill_job_index(db: Session, job_id: Optional[int] = None) -> int:
    query = db.query(Job).join(Company, Job.company_id == Company.id).filter(
        Job.status == "published", Company.verification_status == "da_xac_minh",
        or_(Job.deadline.is_(None), Job.deadline >= date.today()),
    )
    if job_id:
        query = query.filter(Job.id == job_id)
        db.query(SkillJobIndex).filter(SkillJobIndex.job_id == job_id).delete()
    else:
        db.query(SkillJobIndex).delete()

    records, seen = [], set()
    for job in query.all():
        for s in (job.skills or []):
            name, req = (s.get("name", ""), bool(s.get("required", True))) if isinstance(s, dict) else (str(s), True)
            canon = normalize_skill_name(name)
            if canon and (canon, job.id) not in seen:
                seen.add((canon, job.id))
                records.append(SkillJobIndex(skill_canonical=canon, job_id=job.id, is_required=req))
    if records:
        db.bulk_save_objects(records)
    db.commit()
    return len(records)


def parse_candidate_skills(profile: Optional[CandidateProfile]) -> List[str]:
    if not profile or not profile.skills_json:
        return []
    try:
        data = json.loads(profile.skills_json)
        if isinstance(data, list):
            res = []
            for item in data:
                val = (item.get("name", "") if isinstance(item, dict) else str(item)).strip()
                if val and val not in res:
                    res.append(val)
            return res
    except Exception:
        pass
    return []


def get_applied_job_ids(db: Session, user_id: int, profile_id: Optional[int]) -> Set[int]:
    applied: Set[int] = set()
    q1 = db.query(Application.job_id).filter(
        or_(Application.candidate_id == user_id, Application.candidate_profile_id == profile_id)
        if profile_id else (Application.candidate_id == user_id)
    )
    applied.update(r[0] for r in q1.all() if r[0])
    q2 = db.query(JobApplication.job_id).filter(JobApplication.candidate_id == user_id)
    applied.update(r[0] for r in q2.all() if r[0])
    return applied


def compute_and_cache_matches(db: Session, user_id: int) -> Dict[str, Any]:
    settings = get_or_create_candidate_settings(db, user_id)
    if not settings.is_enabled:
        return {"status": "da_tat", "total": 0}

    profile = db.query(CandidateProfile).filter_by(user_id=user_id).first()
    cand_skills = parse_candidate_skills(profile)
    if len(cand_skills) < DEFAULT_CONFIG.min_candidate_skills:
        return {"status": "can_them_ky_nang", "total": 0, "skill_count": len(cand_skills)}

    applied_jobs = get_applied_job_ids(db, user_id, profile.id if profile else None)
    job_query = db.query(Job).join(Company, Job.company_id == Company.id).filter(
        Job.status == "published", Company.verification_status == "da_xac_minh",
        Company.is_visible == True,  # noqa: E712
        or_(Job.deadline.is_(None), Job.deadline >= date.today()),
    )
    if applied_jobs:
        job_query = job_query.filter(Job.id.notin_(applied_jobs))

    active_jobs = job_query.all()
    now_utc = datetime.now(timezone.utc)
    db.query(MatchScore).filter(MatchScore.candidate_id == user_id).delete()
    saved_scores: List[MatchScore] = []

    for job in active_jobs:
        match_res = compute_pure_match(
            job_skills=job.skills or [], job_level=job.level, job_location=job.location,
            job_salary_min=job.salary_min, job_salary_max=job.salary_max,
            job_is_negotiable=job.is_salary_negotiable, cand_skills=cand_skills,
            cand_level=profile.level if profile else None,
            cand_location=profile.location or (profile.address if profile else None),
            cand_open_to_relocate=settings.open_to_relocate,
            cand_expected_salary=profile.expected_salary if profile else None, now=now_utc,
        )
        if match_res and match_res["is_match"]:
            saved_scores.append(MatchScore(
                candidate_id=user_id, job_id=job.id, total_score=match_res["total_score"],
                skill_score=match_res["skill_score"], level_score=match_res["level_score"],
                place_score=match_res["place_score"], salary_score=match_res["salary_score"],
                matched_skills_json=json.dumps(match_res["matched_skills"], ensure_ascii=False),
                missing_required_json=json.dumps(match_res["missing_required"], ensure_ascii=False),
                labels_json=json.dumps(match_res["labels"], ensure_ascii=False),
                formula_version=match_res["formula_version"], computed_at=now_utc, is_dirty=False,
            ))

    if saved_scores:
        db.bulk_save_objects(saved_scores)
    db.commit()
    return {"status": "co_ket_qua" if saved_scores else "rong", "total": len(saved_scores)}


def get_candidate_matches_page(db: Session, user_id: int, page: int = 1, size: int = 10) -> Dict[str, Any]:
    state = compute_and_cache_matches(db, user_id)
    empty_res = {
        "status": state["status"], "items": [], "total": 0, "page": page,
        "size": size, "formula_version": DEFAULT_CONFIG.version, "data_as_of": datetime.now(timezone.utc).isoformat(),
    }
    if state["status"] in ("da_tat", "can_them_ky_nang", "rong"):
        return empty_res

    total = db.query(func.count(MatchScore.id)).filter(MatchScore.candidate_id == user_id).scalar() or 0
    scores = (
        db.query(MatchScore, Job, Company)
        .join(Job, MatchScore.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .filter(MatchScore.candidate_id == user_id)
        .order_by(MatchScore.total_score.desc(), Job.published_at.desc(), Job.id.asc())
        .offset((page - 1) * size).limit(size).all()
    )

    items = []
    for ms, j, c in scores:
        items.append({
            "job_id": j.id, "title": j.title,
            "company": {"id": c.id, "name": c.name, "slug": c.slug, "logo_url": c.logo_url},
            "location": j.location, "level": j.level,
            "salary_display": "Thỏa thuận" if j.is_salary_negotiable and not (j.salary_min or j.salary_max) else f"{j.salary_min or 0} - {j.salary_max or 0}",
            "salary_min": j.salary_min, "salary_max": j.salary_max, "is_salary_negotiable": j.is_salary_negotiable,
            "total_score": round(ms.total_score, 4), "match_percentage": int(round(ms.total_score * 100)),
            "skill_score": round(ms.skill_score, 4), "level_score": round(ms.level_score, 4),
            "place_score": round(ms.place_score, 4), "salary_score": round(ms.salary_score, 4),
            "matched_skills": json.loads(ms.matched_skills_json or "[]"),
            "missing_required": json.loads(ms.missing_required_json or "[]"),
            "labels": json.loads(ms.labels_json or "{}"),
            "published_at": j.published_at.isoformat() if j.published_at else None,
            "formula_version": ms.formula_version,
        })

    return {
        "status": "co_ket_qua" if items else "rong", "items": items, "total": total,
        "page": page, "size": size, "formula_version": DEFAULT_CONFIG.version,
        "data_as_of": datetime.now(timezone.utc).isoformat(),
    }
