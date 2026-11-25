"""Module tính điểm độ phù hợp (Relevance Score) cho việc làm (< 100 dòng)."""
from datetime import datetime, timedelta


def _compute_keyword_score(title: str, skills: list, company_name: str, kw: str) -> float:
    if not kw:
        return 0.0
    score = 0.0
    t_low = (title or "").lower()
    comp_low = (company_name or "").lower()
    skills_low = [str(s).lower() for s in (skills or [])]

    if t_low == kw:
        score += 100.0
    elif t_low.startswith(kw):
        score += 80.0
    elif kw in t_low:
        score += 60.0
    else:
        tokens = [tk for tk in kw.split() if len(tk) >= 2]
        token_hits = sum(1 for tk in tokens if tk in t_low)
        if token_hits:
            score += (token_hits / max(1, len(tokens))) * 50.0

    if any(kw == s for s in skills_low):
        score += 35.0
    elif any(kw in s for s in skills_low):
        score += 25.0

    if kw in comp_low:
        score += 15.0
    return score


def _compute_quality_score(job_item: dict) -> float:
    score = 0.0
    sal_max = job_item.get("salary_max") or 0
    is_neg = bool(job_item.get("is_salary_negotiable"))

    if not is_neg and sal_max > 0:
        score += 30.0
        score += min(20.0, (sal_max / 1_000_000) * 0.3)
    elif is_neg:
        score += 5.0

    if job_item.get("is_verified"):
        score += 25.0

    skills = job_item.get("skills") or []
    if len(skills) >= 3:
        score += 15.0

    c_at = job_item.get("created_at")
    if isinstance(c_at, datetime):
        c_at_naive = c_at.replace(tzinfo=None)
        if (datetime.now() - c_at_naive).days <= 14:
            score += 10.0
    return score


def compute_relevance_score(
    job_item: dict,
    *,
    keyword: str = "",
    candidate_profile: dict | None = None,
    match_score: float | None = None,
) -> float:
    """Tính điểm độ phù hợp tổng hợp (0 - 150+)."""
    kw = (keyword or "").strip().lower()
    title = str(job_item.get("title") or "")
    skills = job_item.get("skills") or []
    comp_name = str(job_item.get("company_name") or "")

    kw_score = _compute_keyword_score(title, skills, comp_name, kw) if kw else 0.0
    quality_score = _compute_quality_score(job_item)
    profile_score = float(match_score) if (candidate_profile and match_score is not None) else 0.0

    if kw and candidate_profile:
        return kw_score * 0.6 + profile_score * 0.3 + quality_score * 0.1
    if kw:
        return kw_score * 0.8 + quality_score * 0.2
    if candidate_profile and match_score is not None:
        return profile_score * 0.75 + quality_score * 0.25
    return quality_score
