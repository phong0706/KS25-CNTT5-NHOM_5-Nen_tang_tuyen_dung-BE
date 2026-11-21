"""Dịch vụ truy vấn, lọc facets và sắp xếp việc làm công khai."""
from datetime import date, datetime
import json
import math
import re

from sqlalchemy import String, and_, case, cast, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaCategory, MetaLevel, MetaLocation, MetaWorkType, SavedJob
from app.models.user import User
from app.schemas.job import FacetItemOut, PublicJobCardOut, PublicJobsFacetsOut, PublicJobsSearchOut
from app.services.matching import compute_job_match
from app.services.salary_insight_service import fetch_peers_salaries_map, get_job_salary_insight


def _split_csv(val: str) -> list[str]:
    return [x.strip() for x in val.split(",") if x.strip()]


def build_public_job_filters(*, q: str = "", location: str = "", level: str = "", work_type: str = "", category: str = "", company_id: int | None = None, company: str = "", salary_min: int | None = None, salary_max: int | None = None, skills: str = "", exclude: str = ""):
    today = date.today()
    comp_ok = or_(Company.verification_status == "da_xac_minh", Company.status == CompanyStatus.VERIFIED, Company.is_verified == True)  # noqa: E712
    conds = [Job.status.in_(["open", "published"]), Job.deleted_at.is_(None), or_(Job.deadline.is_(None), Job.deadline >= today), comp_ok]
    kw = q.strip()
    if kw:
        tokens = [re.sub(r"[^\w]", "", t) for t in kw.replace("-", " ").split()]
        tokens = [t for t in tokens if len(t) >= 2]
        if len(kw) >= 3 and tokens:
            boolean_q = " ".join(f"+{t}*" for t in tokens[:5])
            conds.append(or_(text("MATCH(jobs.title) AGAINST(:ft_q IN BOOLEAN MODE)").bindparams(ft_q=boolean_q), Job.title.ilike(f"%{kw}%")))
        else:
            conds.append(Job.title.ilike(f"%{kw}%"))

    if exclude != "location" and location.strip():
        vals = _split_csv(location)
        conds.append(or_(MetaLocation.slug.in_(vals), MetaLocation.name.in_(vals)))
    if exclude != "level" and level.strip():
        vals = _split_csv(level)
        conds.append(or_(MetaLevel.slug.in_(vals), MetaLevel.name.in_(vals)))
    if exclude != "type" and work_type.strip():
        vals = _split_csv(work_type)
        conds.append(or_(MetaWorkType.slug.in_(vals), MetaWorkType.name.in_(vals)))
    if exclude != "category" and category.strip():
        vals = _split_csv(category)
        conds.append(or_(MetaCategory.slug.in_(vals), MetaCategory.name.in_(vals)))
    if company_id is not None:
        conds.append(Job.company_id == company_id)
    if company.strip():
        conds.append(Company.slug == company.strip().lower())
    if salary_min is not None:
        conds.append(or_(Job.salary_max >= salary_min, Job.salary_min >= salary_min))
    if salary_max is not None:
        conds.append(or_(Job.salary_min <= salary_max, Job.salary_max <= salary_max))
    if skills.strip():
        for sk in _split_csv(skills)[:15]:
            sk_norm = sk.lower().replace("-", " ")
            conds.append(or_(
                func.json_contains(Job.skills, func.json_quote(sk)) == 1,
                func.lower(cast(Job.skills, String(2000))).like(f'%"{sk_norm}"%'),
            ))
    return conds


def count_public_jobs(db: Session, **kwargs) -> int:
    conds = build_public_job_filters(**kwargs)
    stmt = (
        select(func.count(func.distinct(Job.id)))
        .select_from(Job)
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
        .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .where(*conds)
    )
    return int(db.scalar(stmt) or 0)


def _fetch_market_benchmarks(db: Session) -> dict:
    stmt = (
        select(
            Job.category_id, Job.level_id, func.count(Job.id).label("cnt"),
            func.avg((func.coalesce(Job.salary_min, Job.salary_max) + func.coalesce(Job.salary_max, Job.salary_min)) / 2.0).label("avg_sal"),
        )
        .where(Job.status == "published", (Job.salary_min.is_not(None) | Job.salary_max.is_not(None)))
        .group_by(Job.category_id, Job.level_id)
    )
    return {(r.category_id, r.level_id): {"count": int(r.cnt or 0), "avg_salary": float(r.avg_sal or 0)} for r in db.execute(stmt).all()}


def _compute_facet(db: Session, model_cls, fk_col, filter_kwargs: dict, exclude_key: str) -> list[FacetItemOut]:
    conds = build_public_job_filters(**filter_kwargs, exclude=exclude_key)
    subq = (
        select(fk_col.label("meta_id"), func.count(func.distinct(Job.id)).label("cnt"))
        .select_from(Job).outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id).outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id).outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .where(*conds).group_by(fk_col).subquery()
    )
    stmt = (
        select(model_cls.slug, model_cls.name, func.coalesce(subq.c.cnt, 0).label("cnt"))
        .outerjoin(subq, model_cls.id == subq.c.meta_id)
        .order_by(text("cnt DESC"), model_cls.sort_order.asc(), model_cls.id.asc())
    )
    return [FacetItemOut(value=r.slug, label=r.name, count=int(r.cnt)) for r in db.execute(stmt).all()]


def _load_candidate_profile(db: Session, current_user: User | None) -> dict | None:
    if not current_user:
        return None
    prof = db.execute(text("SELECT skills_json, level, location, work_type, expected_salary, headline FROM candidate_profiles WHERE user_id = :uid"), {"uid": current_user.id}).fetchone()
    if not prof or not prof[0]:
        return None
    raw, skills_list = prof[0], []
    if isinstance(raw, list):
        skills_list = [str(s).strip() for s in raw if str(s).strip()]
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            skills_list = [str(s).strip() for s in parsed if str(s).strip()] if isinstance(parsed, list) else [s.strip() for s in str(parsed).split(",") if s.strip()]
        except Exception:
            skills_list = [s.strip() for s in raw.split(",") if s.strip()]
    if not skills_list:
        return None
    c_lvl = prof.level if prof.level else None
    if not c_lvl and prof.headline:
        hl = prof.headline.lower()
        c_lvl = next((k.title() for k in ("senior", "junior", "middle", "intern", "lead") if k in hl), None)
    return {"skills": skills_list, "level": c_lvl, "location": prof.location, "work_type": prof.work_type, "expected_salary": prof.expected_salary}


def query_public_jobs(db: Session, *, q: str, location: str, level: str, work_type: str, category: str, company_id: int | None, company: str, salary_min: int | None, salary_max: int | None, skills: str, sort: str, distinct_company: bool, page: int, page_size: int, current_user: User | None) -> PublicJobsSearchOut:
    f_kwargs = dict(q=q, location=location, level=level, work_type=work_type, category=category, company_id=company_id, company=company, salary_min=salary_min, salary_max=salary_max, skills=skills)
    conds = build_public_job_filters(**f_kwargs)
    count_target = func.distinct(Job.company_id) if distinct_company else func.distinct(Job.id)
    total = int(db.scalar(
        select(func.count(count_target)).select_from(Job).outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id).outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id).outerjoin(MetaCategory, Job.category_id == MetaCategory.id).where(*conds)
    ) or 0)
    total_pages = max(1, math.ceil(total / page_size))
    if page > total_pages:
        facets = PublicJobsFacetsOut(
            location=_compute_facet(db, MetaLocation, Job.location_id, f_kwargs, "location"),
            level=_compute_facet(db, MetaLevel, Job.level_id, f_kwargs, "level"),
            type=_compute_facet(db, MetaWorkType, Job.work_type_id, f_kwargs, "type"),
            category=_compute_facet(db, MetaCategory, Job.category_id, f_kwargs, "category"),
        )
        return PublicJobsSearchOut(items=[], total=total, page=page, page_size=page_size, total_pages=total_pages, facets=facets)

    safe_page = page
    offset = (safe_page - 1) * page_size

    cand_profile_data = _load_candidate_profile(db, current_user)
    use_relevant_sort = sort == "relevant" and cand_profile_data is not None

    if sort == "salary_desc":
        is_neg_expr = case((or_(Job.is_salary_negotiable == True, and_(Job.salary_min.is_(None), Job.salary_max.is_(None))), 1), else_=0)  # noqa: E712
        order_clauses = [is_neg_expr.asc(), func.coalesce(Job.salary_max, Job.salary_min, 0).desc(), func.coalesce(Job.salary_min, Job.salary_max, 0).desc(), func.coalesce(Job.published_at, Job.created_at).desc(), Job.id.desc()]
    else:
        order_clauses = [func.coalesce(Job.published_at, Job.created_at).desc(), Job.id.desc()]

    stmt = (
        select(Job, Company.name.label("company_name"), Company.slug.label("company_slug"), MetaLocation.slug.label("loc_slug"), MetaLevel.slug.label("lvl_slug"), MetaWorkType.slug.label("wt_slug"), MetaCategory.name.label("cat_name"), MetaCategory.slug.label("cat_slug"))
        .outerjoin(Company, Job.company_id == Company.id).outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
        .outerjoin(MetaLevel, Job.level_id == MetaLevel.id).outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id).where(*conds).order_by(*order_clauses)
    )
    if distinct_company:
        ranked = (
            select(
                Job.id.label("jid"),
                func.row_number()
                .over(
                    partition_by=Job.company_id,
                    order_by=[func.coalesce(Job.published_at, Job.created_at).desc(), Job.id.desc()],
                )
                .label("rn"),
            )
            .select_from(Job)
            .outerjoin(Company, Job.company_id == Company.id)
            .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
            .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
            .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
            .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
            .where(*conds)
            .subquery()
        )
        stmt = stmt.add_columns(ranked.c.rn).join(ranked, ranked.c.jid == Job.id).where(ranked.c.rn == 1)

    if use_relevant_sort:
        all_rows = db.execute(stmt).all()
        match_cache = {
            r.Job.id: compute_job_match(cand_profile_data, {"skills": r.Job.skills if isinstance(r.Job.skills, list) else [], "level": r.Job.level, "location": r.Job.location, "work_type": r.Job.work_type, "salary_min": r.Job.salary_min, "salary_max": r.Job.salary_max, "is_salary_negotiable": bool(r.Job.is_salary_negotiable)})
            for r in all_rows
        }
        all_rows.sort(key=lambda r: (match_cache[r.Job.id]["match_score"], (r.Job.published_at or r.Job.created_at or datetime.min).replace(tzinfo=None), r.Job.id), reverse=True)
        rows = all_rows[offset : offset + page_size]
    else:
        match_cache = {}
        rows = db.execute(stmt.offset(offset).limit(page_size)).all()

    saved_ids = set(db.scalars(select(SavedJob.job_id).where(SavedJob.user_id == current_user.id, SavedJob.job_id.in_([r.Job.id for r in rows]))).all()) if (current_user and rows) else set()
    peers_salaries_map = fetch_peers_salaries_map(db)
    items = []
    for r in rows:
        job = r.Job
        m_res = match_cache.get(job.id)
        if not m_res and cand_profile_data:
            m_res = compute_job_match(cand_profile_data, {"skills": job.skills if isinstance(job.skills, list) else [], "level": job.level, "location": job.location, "work_type": job.work_type, "salary_min": job.salary_min, "salary_max": job.salary_max, "is_salary_negotiable": bool(job.is_salary_negotiable)})
        sal_insight, _ = get_job_salary_insight(job, peers_salaries_map)
        items.append(PublicJobCardOut(
            id=job.id, title=(job.title or "").replace("[Seed]", "").strip(), company_id=job.company_id, company_slug=r.company_slug, company_name=r.company_name or "Doanh nghiệp công nghệ",
            location=job.location, location_slug=r.loc_slug, level=job.level, level_slug=r.lvl_slug, work_type=job.work_type, work_type_slug=r.wt_slug,
            category=r.cat_name, category_slug=r.cat_slug, salary_min=job.salary_min, salary_max=job.salary_max, is_salary_negotiable=job.is_salary_negotiable,
            skills=list(job.skills or []), published_at=job.published_at, created_at=job.created_at, is_saved=job.id in saved_ids,
            match_score=m_res["match_score"] if m_res else None, matched_skills=m_res["matched_skills"] if m_res else [],
            missing_skills=m_res["missing_skills"] if m_res else [], match_reason=m_res["reason"] if m_res else None, salary_insight=sal_insight,
        ))
    facets = PublicJobsFacetsOut(
        location=_compute_facet(db, MetaLocation, Job.location_id, f_kwargs, "location"),
        level=_compute_facet(db, MetaLevel, Job.level_id, f_kwargs, "level"),
        type=_compute_facet(db, MetaWorkType, Job.work_type_id, f_kwargs, "type"),
        category=_compute_facet(db, MetaCategory, Job.category_id, f_kwargs, "category"),
    )
    return PublicJobsSearchOut(items=items, total=total, page=safe_page, page_size=page_size, total_pages=total_pages, facets=facets)
