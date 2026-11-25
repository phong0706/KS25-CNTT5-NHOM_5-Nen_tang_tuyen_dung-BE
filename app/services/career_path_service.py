"""Service Lộ trình sự nghiệp (Career Path Engine).
- Tính trọng số w(vai trò, kỹ năng) = số tin yêu cầu kỹ năng / tổng số tin của vai trò
  (trên tin đang mở hoặc trong 180 ngày gần nhất, ngưỡng mẫu tối thiểu MIN_ROLE_SAMPLE_SIZE = 5).
- Lưu vào bảng career_role_stats & career_role_skill_weights và có hàm job cập nhật định kỳ.
- Tính coverage, gap (sắp giảm dần theo w), xếp hạng bước tiếp theo & bước sau nữa.
Giới hạn: < 200 dòng.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import statistics
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.career_path import CareerRoleSkillWeight, CareerRoleStat, CareerRoleTransition
from app.services.matching import normalize_skill_list

MIN_ROLE_SAMPLE_SIZE = 5
MIN_SALARY_SAMPLE_SIZE = 5


def load_db_alias_map(db: Session) -> dict[str, str]:
    try:
        rows = db.execute(text("SELECT sa.alias, ms.name FROM skill_aliases sa JOIN meta_skills ms ON sa.skill_id = ms.id")).fetchall()
        return {str(r[0]).strip().lower(): str(r[1]).strip() for r in rows if r[0] and r[1]}
    except Exception:
        return {}


def _parse_raw_skills(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if str(s).strip()]
        except Exception:
            pass
        return [s.strip() for s in raw.split(",") if s.strip()]
    return []


def compute_role_weights_pure(
    jobs_list: list[dict], alias_map: dict[str, str] | None = None, min_sample: int = MIN_ROLE_SAMPLE_SIZE,
) -> dict[str, dict]:
    """Hàm thuần tính trọng số kỹ năng và thống kê mẫu cho từng vai trò từ danh sách jobs."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    meta_by_role: dict[str, dict] = {}

    for j in jobs_list:
        f_slug = j["family_slug"]
        l_slug = j["level_slug"]
        r_slug = f"{f_slug}:{l_slug}"
        grouped[r_slug].append(j)
        if r_slug not in meta_by_role:
            meta_by_role[r_slug] = {
                "role_slug": r_slug, "role_name": f"{j['level_name']} {j['family_name']}",
                "family_slug": f_slug, "family_name": j["family_name"],
                "level_slug": l_slug, "level_name": j["level_name"], "level_order": int(j["level_order"]),
            }

    results: dict[str, dict] = {}
    for r_slug, r_jobs in grouped.items():
        total = len(r_jobs)
        meta = meta_by_role[r_slug]
        salaries: list[float] = []
        skill_counts: dict[str, int] = defaultdict(int)

        for j in r_jobs:
            for sk in normalize_skill_list(_parse_raw_skills(j.get("skills")), alias_map):
                skill_counts[sk] += 1
            if not j.get("is_salary_negotiable"):
                smin, smax = j.get("salary_min"), j.get("salary_max")
                if smin and smax and smin > 0 and smax > 0:
                    salaries.append((float(smin) + float(smax)) / 2.0)
                elif smax and smax > 0:
                    salaries.append(float(smax))
                elif smin and smin > 0:
                    salaries.append(float(smin))

        is_suff = total >= min_sample
        sal_median = int(round(statistics.median(salaries))) if len(salaries) >= MIN_SALARY_SAMPLE_SIZE else None
        weights_list = [
            {"skill_name": sk, "job_count": cnt, "total_role_jobs": total, "weight": round(cnt / total, 4)}
            for sk, cnt in sorted(skill_counts.items(), key=lambda x: (-x[1], x[0].lower()))
        ] if (is_suff and total > 0) else []

        results[r_slug] = {
            **meta, "sample_size": total, "salary_sample_size": len(salaries),
            "salary_median": sal_median, "is_sufficient": is_suff, "skills": weights_list,
        }
    return results


def evaluate_candidate_against_role(
    cand_skills: list[str], role_stat: dict, role_weights: list[dict], alias_map: dict[str, str] | None = None,
) -> dict:
    """Tính coverage = tổng w kỹ năng ứng viên có / tổng w của vai trò, và gap giảm dần theo w."""
    norm_cand = normalize_skill_list(cand_skills, alias_map)
    cand_lower_map = {s.lower(): s for s in norm_cand}

    total_w = sum(float(item["weight"]) for item in role_weights)
    matched_w = 0.0
    matched_skills: list[dict] = []
    missing_skills: list[dict] = []

    sorted_weights = sorted(role_weights, key=lambda x: (-float(x["weight"]), str(x["skill_name"]).lower()))
    for item in sorted_weights:
        sk_name = item["skill_name"]
        entry = {
            "name": sk_name, "weight": round(float(item["weight"]), 4),
            "job_count": int(item.get("job_count", 0)),
            "total_role_jobs": int(item.get("total_role_jobs", role_stat.get("sample_size", 0))),
        }
        if sk_name.lower() in cand_lower_map:
            matched_w += float(item["weight"])
            matched_skills.append(entry)
        else:
            missing_skills.append(entry)

    coverage = round(matched_w / total_w, 4) if total_w > 0 else 0.0
    total_sk, matched_cnt = len(sorted_weights), len(matched_skills)

    return {
        "role_slug": role_stat["role_slug"], "role": role_stat["role_name"],
        "family_slug": role_stat["family_slug"], "family_name": role_stat["family_name"],
        "level": role_stat["level_name"], "level_slug": role_stat["level_slug"],
        "level_order": int(role_stat["level_order"]),
        "status": "ok" if role_stat.get("is_sufficient") else "insufficient_data",
        "coverage": coverage, "coverage_percent": int(round(coverage * 100)),
        "matched_skill_count": matched_cnt, "total_skill_count": total_sk,
        "coverage_label": f"{matched_cnt}/{total_sk} kỹ năng",
        "missing_skill_count": len(missing_skills),
        "matched_skills": matched_skills, "missing_skills": missing_skills,
        "salary_median": role_stat.get("salary_median"),
        "salary_sample_size": int(role_stat.get("salary_sample_size") or 0),
        "sample_size": int(role_stat.get("sample_size") or 0),
        "data_as_of": role_stat.get("data_as_of"),
    }


def refresh_career_weights_in_db(db: Session) -> dict:
    """Job cập nhật định kỳ trọng số kỹ năng theo vai trò vào bảng riêng trong MySQL."""
    alias_map = load_db_alias_map(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    now_utc = datetime.now(timezone.utc)

    # Seed cấu hình đường đi chuyển họ mặc định nếu bảng trống
    if (db.scalar(select(CareerRoleTransition.id).limit(1))) is None:
        default_transitions = [
            CareerRoleTransition(from_family_slug="backend", to_family_slug="devops-cloud", min_level_order=4, is_active=True, note="Backend chuyển sang DevOps & Cloud từ cấp Middle"),
            CareerRoleTransition(from_family_slug="backend", to_family_slug="ai-data", min_level_order=4, is_active=True, note="Backend chuyển sang AI & Data từ cấp Middle"),
            CareerRoleTransition(from_family_slug="frontend", to_family_slug="mobile", min_level_order=3, is_active=True, note="Frontend chuyển sang Mobile App từ cấp Junior"),
            CareerRoleTransition(from_family_slug="qa-testing", to_family_slug="devops-cloud", min_level_order=4, is_active=True, note="QA Automation chuyển sang DevOps từ cấp Middle"),
        ]
        db.add_all(default_transitions)
        db.flush()

    cats = db.execute(text("SELECT id, slug, name FROM meta_categories ORDER BY sort_order")).fetchall()
    lvls = db.execute(text("SELECT id, slug, name, sort_order FROM meta_levels ORDER BY sort_order")).fetchall()
    rows = db.execute(
        text("SELECT j.id, j.skills, j.salary_min, j.salary_max, j.is_salary_negotiable, c.slug AS family_slug, c.name AS family_name, l.slug AS level_slug, l.name AS level_name, l.sort_order AS level_order FROM jobs j JOIN meta_categories c ON j.category_id = c.id JOIN meta_levels l ON j.level_id = l.id WHERE j.status = 'published' OR j.published_at >= :cutoff OR j.created_at >= :cutoff"),
        {"cutoff": cutoff},
    ).fetchall()
    computed = compute_role_weights_pure([dict(r._mapping) for r in rows], alias_map=alias_map, min_sample=MIN_ROLE_SAMPLE_SIZE)
    db.query(CareerRoleSkillWeight).delete()
    db.query(CareerRoleStat).delete()
    db.flush()

    sufficient_cnt, insufficient_cnt = 0, 0
    for c in cats:
        for l in lvls:
            r_slug = f"{c.slug}:{l.slug}"
            info = computed.get(r_slug) or {
                "role_slug": r_slug, "role_name": f"{l.name} {c.name}",
                "family_slug": c.slug, "family_name": c.name,
                "level_slug": l.slug, "level_name": l.name, "level_order": int(l.sort_order),
                "sample_size": 0, "salary_sample_size": 0, "salary_median": None, "is_sufficient": False, "skills": [],
            }
            sufficient_cnt += 1 if info["is_sufficient"] else 0
            insufficient_cnt += 0 if info["is_sufficient"] else 1

            db.add(CareerRoleStat(
                role_slug=r_slug, role_name=info["role_name"], family_slug=info["family_slug"],
                family_name=info["family_name"], level_slug=info["level_slug"], level_name=info["level_name"],
                level_order=info["level_order"], sample_size=info["sample_size"],
                salary_sample_size=info["salary_sample_size"], salary_median=info["salary_median"],
                is_sufficient=info["is_sufficient"], data_as_of=now_utc,
            ))
            for sk_item in info["skills"]:
                db.add(CareerRoleSkillWeight(
                    role_slug=r_slug, skill_name=sk_item["skill_name"], job_count=sk_item["job_count"],
                    total_role_jobs=sk_item["total_role_jobs"], weight=sk_item["weight"], data_as_of=now_utc,
                ))

    db.commit()
    return {"sufficient_roles": sufficient_cnt, "insufficient_roles": insufficient_cnt, "data_as_of": now_utc.isoformat()}
