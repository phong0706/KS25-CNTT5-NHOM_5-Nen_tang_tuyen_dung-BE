"""Router Lộ trình sự nghiệp cho ứng viên (/api/career-path).
Đọc trọng số kỹ năng đã tính sẵn từ bảng career_role_stats & career_role_skill_weights,
gợi ý bước hiện tại, bước tiếp theo (+1 bậc / chuyển họ qua bảng transitions) và bước sau nữa (+2 bậc).
Giới hạn: < 200 dòng.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import get_optional_user, role_required
from app.db.session import get_db
from app.models.career_path import CareerRoleSkillWeight, CareerRoleStat, CareerRoleTransition
from app.models.user import User
from app.services.career_path_service import (
    MIN_ROLE_SAMPLE_SIZE,
    _parse_raw_skills,
    evaluate_candidate_against_role,
    load_db_alias_map,
    refresh_career_weights_in_db,
)
from app.services.matching import normalize_skill_list

router = APIRouter(prefix="/career-path", tags=["Career Path"])


class CareerPathRequest(BaseModel):
    user_id: Optional[int] = None
    skills: Optional[list[str]] = None
    current_family_slug: Optional[str] = None
    current_level_slug: Optional[str] = None


class TransitionIn(BaseModel):
    from_family_slug: str
    to_family_slug: str
    min_level_order: int = 4
    is_active: bool = True
    note: Optional[str] = None


def _ensure_weights_seeded(db: Session):
    if db.scalar(select(CareerRoleStat.id).limit(1)) is None:
        refresh_career_weights_in_db(db)


def _load_related_jobs(db: Session, family_slug: str, level_slug: str, limit: int = 4) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT j.id, j.title, comp.name AS company_name, j.location,
                   j.salary_min, j.salary_max, j.is_salary_negotiable
            FROM jobs j
            JOIN meta_categories c ON j.category_id = c.id
            JOIN meta_levels l ON j.level_id = l.id
            LEFT JOIN companies comp ON j.company_id = comp.id
            WHERE j.status = 'published' AND c.slug = :f_slug AND l.slug = :l_slug
            ORDER BY j.id DESC LIMIT :lim
        """),
        {"f_slug": family_slug, "l_slug": level_slug, "lim": limit},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _build_step_payload(
    db: Session,
    stat: CareerRoleStat,
    weights_by_role: dict[str, list[dict]],
    cand_skills: list[str],
    alias_map: dict[str, str],
    stage: str,
    transition_type: str = "same_family",
    transition_note: str | None = None,
) -> dict:
    stat_dict = {
        "role_slug": stat.role_slug,
        "role_name": stat.role_name,
        "family_slug": stat.family_slug,
        "family_name": stat.family_name,
        "level_slug": stat.level_slug,
        "level_name": stat.level_name,
        "level_order": stat.level_order,
        "sample_size": stat.sample_size,
        "salary_sample_size": stat.salary_sample_size,
        "salary_median": stat.salary_median,
        "is_sufficient": stat.is_sufficient,
        "data_as_of": stat.data_as_of.strftime("%Y-%m-%d") if stat.data_as_of else None,
    }
    related = _load_related_jobs(db, stat.family_slug, stat.level_slug)
    if not stat.is_sufficient:
        return {
            **stat_dict,
            "role": stat.role_name,
            "level": stat.level_name,
            "stage": stage,
            "transition_type": transition_type,
            "transition_note": transition_note,
            "status": "insufficient_data",
            "reason": f"Chưa đủ dữ liệu mẫu để tính trọng số cho vai trò {stat.role_name} (hiện có {stat.sample_size}/{MIN_ROLE_SAMPLE_SIZE} tin tuyển dụng).",
            "coverage": None,
            "coverage_percent": None,
            "matched_skill_count": 0,
            "total_skill_count": 0,
            "coverage_label": None,
            "missing_skill_count": 0,
            "matched_skills": [],
            "missing_skills": [],
            "related_jobs": related,
        }
    evaluated = evaluate_candidate_against_role(
        cand_skills, stat_dict, weights_by_role.get(stat.role_slug, []), alias_map
    )
    evaluated["stage"] = stage
    evaluated["transition_type"] = transition_type
    evaluated["transition_note"] = transition_note
    evaluated["related_jobs"] = related
    return evaluated


def _resolve_roadmap(
    db: Session,
    user_id: int | None,
    skills: list[str] | None,
    family_slug: str | None,
    level_slug: str | None,
) -> dict:
    _ensure_weights_seeded(db)
    alias_map = load_db_alias_map(db)

    cand_skills = list(skills or [])
    inferred_family = family_slug
    inferred_level = level_slug

    if user_id:
        prof = db.execute(
            text("SELECT skills_json, level, headline FROM candidate_profiles WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchone()
        if prof:
            if not cand_skills and prof.skills_json:
                cand_skills = _parse_raw_skills(prof.skills_json)
        if not cand_skills:
            cs_rows = db.execute(
                text("SELECT skill_name FROM candidate_skills WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchall()
            cand_skills = [str(r[0]).strip() for r in cs_rows if r[0]]
        if not cand_skills:
            cand_skills = ["Python", "FastAPI", "MySQL", "Docker", "Redis"]
            if not inferred_level and prof.level:
                l_low = prof.level.strip().lower()
                for slug_k in ("intern", "fresher", "junior", "middle", "senior", "lead-manager"):
                    if slug_k.split("-")[0] in l_low:
                        inferred_level = slug_k
                        break
            if not inferred_family and prof.headline:
                hl = prof.headline.lower()
                if "frontend" in hl or "react" in hl or "vue" in hl:
                    inferred_family = "frontend"
                elif "devops" in hl or "cloud" in hl or "sre" in hl:
                    inferred_family = "devops-cloud"
                elif "qa" in hl or "test" in hl:
                    inferred_family = "qa-testing"
                elif "mobile" in hl or "flutter" in hl or "ios" in hl:
                    inferred_family = "mobile"
                elif "ai" in hl or "data" in hl:
                    inferred_family = "ai-data"
                else:
                    inferred_family = "backend"

    norm_cand_skills = normalize_skill_list(cand_skills, alias_map)
    cur_family = inferred_family or "backend"
    cur_level = inferred_level or "middle"

    all_stats = db.scalars(select(CareerRoleStat)).all()
    stats_map = {s.role_slug: s for s in all_stats}
    all_weights = db.scalars(select(CareerRoleSkillWeight)).all()
    weights_by_role: dict[str, list[dict]] = {}
    for w in all_weights:
        weights_by_role.setdefault(w.role_slug, []).append({
            "skill_name": w.skill_name,
            "weight": w.weight,
            "job_count": w.job_count,
            "total_role_jobs": w.total_role_jobs,
        })

    cur_slug = f"{cur_family}:{cur_level}"
    cur_stat = stats_map.get(cur_slug) or stats_map.get("backend:middle")
    if not cur_stat:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình vai trò.")

    current_step = _build_step_payload(db, cur_stat, weights_by_role, norm_cand_skills, alias_map, "current")

    # Tìm ứng viên bước tiếp theo: cùng họ +1 bậc, hoặc chuyển họ hợp lệ trong bảng transitions
    transitions = db.scalars(
        select(CareerRoleTransition).where(
            CareerRoleTransition.from_family_slug == cur_stat.family_slug,
            CareerRoleTransition.is_active == True,  # noqa: E712
            CareerRoleTransition.min_level_order <= cur_stat.level_order,
        )
    ).all()
    allowed_cross = {t.to_family_slug: t.note for t in transitions}

    next_sufficient: list[dict] = []
    next_insufficient: list[dict] = []
    further_steps: list[dict] = []

    for s in all_stats:
        # 1. Cùng họ, cấp cao hơn 1 bậc
        if s.family_slug == cur_stat.family_slug and s.level_order == cur_stat.level_order + 1:
            step = _build_step_payload(db, s, weights_by_role, norm_cand_skills, alias_map, "next", "same_family")
            (next_sufficient if s.is_sufficient else next_insufficient).append(step)
        # 2. Chuyển họ theo bảng transitions (cùng cấp hoặc cao hơn 1 bậc)
        elif s.family_slug in allowed_cross and s.level_order in (cur_stat.level_order, cur_stat.level_order + 1):
            step = _build_step_payload(
                db, s, weights_by_role, norm_cand_skills, alias_map, "next", "cross_family", allowed_cross[s.family_slug]
            )
            (next_sufficient if s.is_sufficient else next_insufficient).append(step)
        # 3. Bước sau nữa (+2 bậc cùng họ hoặc họ chuyển đổi)
        elif (s.family_slug == cur_stat.family_slug or s.family_slug in allowed_cross) and s.level_order == cur_stat.level_order + 2:
            t_type = "same_family" if s.family_slug == cur_stat.family_slug else "cross_family"
            further_steps.append(
                _build_step_payload(db, s, weights_by_role, norm_cand_skills, alias_map, "further", t_type, allowed_cross.get(s.family_slug))
            )

    # Xếp hạng: coverage giảm dần, rồi số kỹ năng thiếu tăng dần
    next_sufficient.sort(key=lambda x: (-float(x["coverage"] or 0.0), int(x["missing_skill_count"]), x["role"]))
    further_steps.sort(key=lambda x: (x["status"] != "ok", -float(x["coverage"] or 0.0), int(x["missing_skill_count"] or 999)))

    overall_status = "ok" if next_sufficient else "insufficient_data"
    overall_reason = None
    if not next_sufficient:
        overall_reason = (
            f"Các vai trò bậc tiếp theo từ {cur_stat.role_name} hiện chưa đủ tối thiểu "
            f"{MIN_ROLE_SAMPLE_SIZE} tin tuyển dụng đang mở để tính trọng số kỹ năng đáng tin cậy."
        )

    families = [
        {"slug": r[0], "name": r[1]}
        for r in db.execute(text("SELECT slug, name FROM meta_categories ORDER BY sort_order")).fetchall()
    ]
    levels = [
        {"slug": r[0], "name": r[1], "order": r[2]}
        for r in db.execute(text("SELECT slug, name, sort_order FROM meta_levels ORDER BY sort_order")).fetchall()
    ]

    return {
        "status": overall_status,
        "reason": overall_reason,
        "min_sample_size": MIN_ROLE_SAMPLE_SIZE,
        "data_as_of": current_step.get("data_as_of"),
        "candidate_skills": norm_cand_skills,
        "current_step": current_step,
        "next_steps": next_sufficient,
        "insufficient_next_steps": next_insufficient,
        "further_steps": further_steps,
        "available_families": families,
        "available_levels": levels,
        "configured_transitions": [
            {
                "id": t.id,
                "from_family_slug": t.from_family_slug,
                "to_family_slug": t.to_family_slug,
                "min_level_order": t.min_level_order,
                "note": t.note,
            }
            for t in db.scalars(select(CareerRoleTransition).where(CareerRoleTransition.is_active == True)).all()  # noqa: E712
        ],
    }


@router.get("", summary="Gợi ý lộ trình sự nghiệp cho ứng viên (GET)")
def get_career_path(
    user_id: Optional[int] = Query(None),
    skills: Optional[str] = Query(None, description="Danh sách kỹ năng phân tách bằng dấu phẩy"),
    family: Optional[str] = Query(None, description="Slug họ nghề hiện tại (vd: backend, frontend)"),
    level: Optional[str] = Query(None, description="Slug cấp bậc hiện tại (vd: junior, middle, senior)"),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    eff_uid = user_id or (current_user.id if current_user and current_user.role == "candidate" else None)
    parsed_skills = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    return _resolve_roadmap(db, eff_uid, parsed_skills, family, level)


@router.post("", summary="Gợi ý lộ trình sự nghiệp nhận danh sách kỹ năng từ body (POST)")
def post_career_path(
    payload: CareerPathRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    eff_uid = payload.user_id or (current_user.id if current_user and current_user.role == "candidate" else None)
    return _resolve_roadmap(db, eff_uid, payload.skills, payload.current_family_slug, payload.current_level_slug)


@router.post("/refresh", summary="Job cập nhật lại bảng trọng số kỹ năng theo vai trò")
def trigger_refresh_career_weights(
    current_user: User = Depends(role_required("admin", "operator")),
    db: Session = Depends(get_db),
):
    return refresh_career_weights_in_db(db)
