"""Router gợi ý việc làm phù hợp cho ứng viên (/api/candidate/jobs/recommended).
Tuân thủ techrecruit-rules: < 200 dòng, không chia cho 0, cache theo hash hồ sơ, sắp xếp ổn định.
"""
from datetime import datetime
import hashlib, json, math, time
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.job import Job, SavedJob
from app.models.user import User
from app.schemas.job import CandidateProfileSummaryOut, PublicJobCardOut, RecommendedJobsOut
from app.services.matching import compute_job_match, normalize_skill_list

router = APIRouter(prefix="/candidate/jobs/recommended", tags=["Candidate Recommended Jobs"])
_RECOMMENDED_CACHE: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL = 300


def _parse_skills(raw) -> list[str]:
    if not raw: return []
    if isinstance(raw, list): return [str(s).strip() for s in raw if str(s).strip()]
    try:
        p = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(p, list): return [str(s).strip() for s in p if str(s).strip()]
    except Exception: pass
    return [s.strip() for s in str(raw).split(",") if s.strip()]


@router.get("", response_model=RecommendedJobsOut, summary="Gợi ý việc làm theo độ khớp hồ sơ")
def get_recommended_jobs(
    min_score: int = Query(0, ge=0, le=100, description="Điểm khớp tối thiểu (0, 40, 70)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    prof = db.execute(
        text("SELECT skills_json, level, location, work_type, expected_salary, updated_at, headline FROM candidate_profiles WHERE user_id = :uid"),
        {"uid": current_user.id}
    ).fetchone()

    skills_raw = prof.skills_json if prof else None
    cand_skills = normalize_skill_list(_parse_skills(skills_raw))
    cand_level = prof.level if prof and prof.level else None
    if not cand_level and prof and prof.headline:
        hl = prof.headline.lower()
        cand_level = next((k.title() for k in ("senior", "junior", "middle", "intern", "lead") if k in hl), None)

    cand_loc, cand_wt, cand_salary = (prof.location if prof else None), (prof.work_type if prof else None), (prof.expected_salary if prof else None)
    summary_parts = [f"Dựa trên {len(cand_skills)} kỹ năng"]
    if cand_level: summary_parts.append(cand_level)
    if cand_loc: summary_parts.append(cand_loc)

    profile_summary = CandidateProfileSummaryOut(
        skills_count=len(cand_skills), skills=cand_skills, level=cand_level,
        location=cand_loc, work_type=cand_wt, summary_text=", ".join(summary_parts),
    )

    if not cand_skills:
        return RecommendedJobsOut(
            has_skills=False, profile=profile_summary, items=[], total=0,
            page=page, page_size=page_size, total_pages=0,
            message="Hồ sơ của bạn chưa có kỹ năng nào. Vui lòng cập nhật kỹ năng để xem việc làm phù hợp!",
        )

    cand_data = {"skills": cand_skills, "level": cand_level, "location": cand_loc, "work_type": cand_wt, "expected_salary": cand_salary}
    upd_str = str(prof.updated_at) if prof and prof.updated_at else ""
    prof_hash = hashlib.sha256(f"{skills_raw}:{cand_level}:{cand_loc}:{cand_wt}:{cand_salary}:{upd_str}".encode()).hexdigest()
    cache_key = f"{current_user.id}:{prof_hash}"

    now_ts = time.time()
    scored_jobs = None
    if cache_key in _RECOMMENDED_CACHE:
        c_ts, c_list = _RECOMMENDED_CACHE[cache_key]
        if now_ts - c_ts < CACHE_TTL: scored_jobs = c_list

    if scored_jobs is None:
        applied_job_ids = set(db.execute(text("SELECT job_id FROM job_applications WHERE candidate_id = :uid"), {"uid": current_user.id}).scalars().all())
        raw_jobs = db.execute(text("""
            SELECT j.id, j.title, j.company_id, c.slug as company_slug, c.name as company_name, j.location, j.level,
                   j.work_type, j.salary_min, j.salary_max, j.is_salary_negotiable,
                   j.skills, j.deadline, j.published_at, j.created_at
            FROM jobs j LEFT JOIN companies c ON j.company_id = c.id WHERE j.status = 'published'
        """)).fetchall()

        scored_jobs = []
        for r in raw_jobs:
            if r.id in applied_job_ids: continue
            j_skills = _parse_skills(r.skills)
            j_data = {
                "skills": j_skills, "level": r.level, "location": r.location,
                "work_type": r.work_type, "salary_min": r.salary_min, "salary_max": r.salary_max,
                "is_salary_negotiable": bool(r.is_salary_negotiable),
            }
            m_res = compute_job_match(cand_data, j_data)
            scored_jobs.append({
                "raw": r, "clean_skills": j_skills, "match_score": m_res["match_score"],
                "matched_skills": m_res["matched_skills"], "missing_skills": m_res["missing_skills"],
                "match_reason": m_res["reason"],
            })

        scored_jobs.sort(key=lambda x: (x["match_score"], x["raw"].published_at or x["raw"].created_at or datetime.min, x["raw"].id), reverse=True)
        _RECOMMENDED_CACHE[cache_key] = (now_ts, scored_jobs)

    filtered = [j for j in scored_jobs if j["match_score"] >= min_score]
    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    offset = (page - 1) * page_size
    page_slice = filtered[offset : offset + page_size]

    saved_ids = set()
    if page_slice:
        jids = [x["raw"].id for x in page_slice]
        saved_ids = set(db.execute(select(SavedJob.job_id).where(SavedJob.user_id == current_user.id, SavedJob.job_id.in_(jids))).scalars().all())

    items = [
        PublicJobCardOut(
            id=e["raw"].id, title=(e["raw"].title or "").replace("[Seed]", "").strip(),
            company_id=e["raw"].company_id, company_slug=e["raw"].company_slug, company_name=e["raw"].company_name or "Doanh nghiệp tuyển dụng",
            location=e["raw"].location, level=e["raw"].level, work_type=e["raw"].work_type,
            salary_min=e["raw"].salary_min, salary_max=e["raw"].salary_max,
            is_salary_negotiable=bool(e["raw"].is_salary_negotiable), skills=e["clean_skills"],
            published_at=e["raw"].published_at, created_at=e["raw"].created_at,
            is_saved=e["raw"].id in saved_ids, is_expired=False, deadline=e["raw"].deadline,
            match_score=e["match_score"], matched_skills=e["matched_skills"],
            missing_skills=e["missing_skills"], match_reason=e["match_reason"],
        )
        for e in page_slice
    ]

    return RecommendedJobsOut(has_skills=True, profile=profile_summary, items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
