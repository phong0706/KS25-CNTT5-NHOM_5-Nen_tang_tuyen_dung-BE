"""Dịch vụ danh sách Công ty công khai (/api/companies): lọc, facets, tìm kiếm bỏ dấu, không N+1."""
from collections import Counter
from datetime import date
import time
from sqlalchemy import String, and_, case, cast, collate, func, literal, or_, select, text, union_all
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job, MetaCategory, MetaLocation
from app.schemas.company import (
    CompanyFacetItemOut, CompanyFacetsOut, CompanyIndustryOut,
    CompanySalaryRangeOut, CompanyTopSkillOut, PublicCompanyCardOut, PublicCompanyListOut,
)
from app.services.public_company_rules import (
    VALID_SIZE_RANGES, escape_like, slugify_skill, validate_company_media_url, validate_company_website,
)

_SKILL_MAP_CACHE: tuple[float, dict[str, str]] | None = None


def open_job_conds(company_id: int | None = None):
    today = date.today()
    conds = [Job.status == "published", or_(Job.deadline.is_(None), Job.deadline >= today)]
    if company_id is not None:
        conds.append(Job.company_id == company_id)
    return conds


def job_agg_subquery():
    non_neg_min = case((and_(Job.is_salary_negotiable == False, Job.salary_min.is_not(None)), Job.salary_min), else_=None)  # noqa: E712
    non_neg_max = case((and_(Job.is_salary_negotiable == False, Job.salary_max.is_not(None)), Job.salary_max), else_=None)  # noqa: E712
    sal_cnt = case((and_(Job.is_salary_negotiable == False, or_(Job.salary_min.is_not(None), Job.salary_max.is_not(None))), 1), else_=0)  # noqa: E712
    return (
        select(
            Job.company_id.label("company_id"),
            func.count(Job.id).label("open_jobs"),
            func.min(non_neg_min).label("min_salary"),
            func.max(non_neg_max).label("max_salary"),
            func.sum(sal_cnt).label("salary_sample_size"),
            func.max(func.coalesce(Job.published_at, Job.created_at)).label("latest_job_at"),
        )
        .where(*open_job_conds())
        .group_by(Job.company_id)
        .subquery()
    )


def _load_skill_canonical_map(db: Session) -> dict[str, str]:
    global _SKILL_MAP_CACHE
    now = time.monotonic()
    if _SKILL_MAP_CACHE and now - _SKILL_MAP_CACHE[0] < 60:
        return _SKILL_MAP_CACHE[1]
    cmap: dict[str, str] = {}
    try:
        rows = db.execute(
            text("SELECT s.name, s.canonical_name, sa.alias FROM skills s LEFT JOIN skill_aliases sa ON sa.skill_id = s.id")
        ).all()
        for name, canonical, alias in rows:
            canon = (canonical or name or "").strip()
            if not canon:
                continue
            cmap[str(name).strip().lower()] = canon
            cmap[canon.lower()] = canon
            if alias:
                cmap[str(alias).strip().lower()] = canon
    except Exception:
        pass
    _SKILL_MAP_CACHE = (now, cmap)
    return cmap


def extract_top_skills_by_company(db: Session, company_ids: list[int], limit: int) -> dict[int, list[CompanyTopSkillOut]]:
    if not company_ids:
        return {}
    cmap = _load_skill_canonical_map(db)
    counters: dict[int, Counter[str]] = {cid: Counter() for cid in company_ids}
    rows = db.execute(select(Job.company_id, Job.skills).where(*open_job_conds(), Job.company_id.in_(company_ids))).all()
    for cid, skills_val in rows:
        if not isinstance(skills_val, list):
            continue
        seen_in_job: set[str] = set()
        for raw in skills_val:
            txt = str(raw or "").strip()
            if not txt:
                continue
            canon = cmap.get(txt.lower(), txt)
            if canon not in seen_in_job:
                seen_in_job.add(canon)
                counters[cid][canon] += 1
    out: dict[int, list[CompanyTopSkillOut]] = {}
    for cid, cnt in counters.items():
        ranked = sorted(cnt.items(), key=lambda x: (-x[1], slugify_skill(x[0]), x[0].lower()))[:limit]
        out[cid] = [CompanyTopSkillOut(slug=slugify_skill(n), name=n, count=c) for n, c in ranked]
    return out


def safe_media(url: str | None) -> str | None:
    try:
        return validate_company_media_url(url)
    except ValueError:
        return None


def safe_site(url: str | None) -> str | None:
    try:
        return validate_company_website(url)
    except ValueError:
        return None


def build_company_card(c: Company, ind_slug: str | None, ind_name: str | None, loc_name: str | None, agg_row, top_skills: list[str]) -> PublicCompanyCardOut:
    open_jobs = int(agg_row.open_jobs or 0) if agg_row else 0
    sal = None
    if agg_row and int(agg_row.salary_sample_size or 0) > 0 and agg_row.min_salary is not None and agg_row.max_salary is not None:
        sal = CompanySalaryRangeOut(min=int(agg_row.min_salary), max=int(agg_row.max_salary))
    return PublicCompanyCardOut(
        slug=c.slug or str(c.id), name=c.name,
        logo_url=safe_media(c.logo_url if c.logo_status != "removed" else None),
        industry=CompanyIndustryOut(slug=ind_slug, name=ind_name) if ind_slug and ind_name else None,
        location=loc_name or c.address, size_range=c.size_range, is_verified=bool(c.is_verified),
        open_jobs=open_jobs, salary=sal, top_skills=top_skills[:3],
        latest_job_at=agg_row.latest_job_at if agg_row else None,
    )


def _filter_clauses(job_agg, *, q: str, industry: str, location: str, size: str, hiring: int, exclude: str | None = None):
    clauses = [Company.is_visible == True, Company.is_draft == False]  # noqa: E712
    esc_q = escape_like(q)
    if esc_q:
        clauses.append(Company.search_text.like(f"%{esc_q}%", escape="\\"))
    if industry and exclude != "industry":
        clauses.append(MetaCategory.slug == industry.strip().lower())
    if location and exclude != "location":
        clauses.append(MetaLocation.slug == location.strip().lower())
    if size and exclude != "size":
        clauses.append(Company.size_range == size.strip())
    if hiring == 1:
        clauses.append(func.coalesce(job_agg.c.open_jobs, 0) > 0)
    return clauses


def _col(expr):
    return collate(cast(expr, String(160)), "utf8mb4_unicode_ci")


def _fetch_facets(db: Session, agg, *, q: str, industry: str, location: str, size: str, hiring: int) -> CompanyFacetsOut:
    q_ind = select(_col(literal("industry")).label("kind"), _col(MetaCategory.slug).label("val"), _col(MetaCategory.name).label("lbl"), func.count(Company.id).label("cnt")).join(Company, Company.industry_id == MetaCategory.id).outerjoin(MetaLocation, Company.location_id == MetaLocation.id).outerjoin(agg, Company.id == agg.c.company_id).where(*_filter_clauses(agg, q=q, industry=industry, location=location, size=size, hiring=hiring, exclude="industry")).group_by(MetaCategory.slug, MetaCategory.name)
    q_loc = select(_col(literal("location")).label("kind"), _col(MetaLocation.slug).label("val"), _col(MetaLocation.name).label("lbl"), func.count(Company.id).label("cnt")).join(Company, Company.location_id == MetaLocation.id).outerjoin(MetaCategory, Company.industry_id == MetaCategory.id).outerjoin(agg, Company.id == agg.c.company_id).where(*_filter_clauses(agg, q=q, industry=industry, location=location, size=size, hiring=hiring, exclude="location")).group_by(MetaLocation.slug, MetaLocation.name)
    q_sz = select(_col(literal("size")).label("kind"), _col(Company.size_range).label("val"), _col(Company.size_range).label("lbl"), func.count(Company.id).label("cnt")).outerjoin(MetaCategory, Company.industry_id == MetaCategory.id).outerjoin(MetaLocation, Company.location_id == MetaLocation.id).outerjoin(agg, Company.id == agg.c.company_id).where(*_filter_clauses(agg, q=q, industry=industry, location=location, size=size, hiring=hiring, exclude="size"), Company.size_range.is_not(None)).group_by(Company.size_range)

    rows = db.execute(union_all(q_ind, q_loc, q_sz)).all()
    ind_items = sorted([CompanyFacetItemOut(value=v, label=l, count=int(c)) for k, v, l, c in rows if k == "industry"], key=lambda x: (-x.count, x.label))
    loc_items = sorted([CompanyFacetItemOut(value=v, label=l, count=int(c)) for k, v, l, c in rows if k == "location"], key=lambda x: (-x.count, x.label))
    size_map = {str(v): int(c) for k, v, _, c in rows if k == "size"}
    sz_items = [CompanyFacetItemOut(value=s, label=f"{s} nhân viên", count=size_map[s]) for s in VALID_SIZE_RANGES if size_map.get(s, 0) > 0]
    return CompanyFacetsOut(industry=ind_items, location=loc_items, size=sz_items)


def list_public_companies(
    db: Session, *, q: str, industry: str, location: str, size: str, hiring: int, sort: str, page: int, page_size: int
) -> PublicCompanyListOut:
    agg = job_agg_subquery()
    base_from = (
        select(Company, MetaCategory.slug.label("ind_slug"), MetaCategory.name.label("ind_name"), MetaLocation.name.label("loc_name"), agg)
        .outerjoin(MetaCategory, Company.industry_id == MetaCategory.id)
        .outerjoin(MetaLocation, Company.location_id == MetaLocation.id)
        .outerjoin(agg, Company.id == agg.c.company_id)
    )
    where_main = _filter_clauses(agg, q=q, industry=industry, location=location, size=size, hiring=hiring)
    tot_row = db.execute(
        select(func.count(Company.id), func.coalesce(func.sum(agg.c.open_jobs), 0))
        .select_from(Company).outerjoin(MetaCategory, Company.industry_id == MetaCategory.id).outerjoin(MetaLocation, Company.location_id == MetaLocation.id).outerjoin(agg, Company.id == agg.c.company_id)
        .where(*where_main)
    ).one()
    total, hiring_total = int(tot_row[0] or 0), int(tot_row[1] or 0)

    open_col = func.coalesce(agg.c.open_jobs, 0)
    order = (
        [Company.name.asc(), Company.id.asc()] if sort == "name"
        else [case((agg.c.latest_job_at.is_(None), 1), else_=0).asc(), agg.c.latest_job_at.desc(), Company.name.asc()] if sort == "recent"
        else [open_col.desc(), Company.name.asc(), Company.id.asc()]
    )
    rows = db.execute(base_from.where(*where_main).order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    skill_map = extract_top_skills_by_company(db, [r[0].id for r in rows], 3)
    items = [build_company_card(r[0], r.ind_slug, r.ind_name, r.loc_name, r, [s.name for s in skill_map.get(r[0].id, [])]) for r in rows]
    facets = _fetch_facets(db, agg, q=q, industry=industry, location=location, size=size, hiring=hiring)
    return PublicCompanyListOut(items=items, total=total, page=page, page_size=page_size, hiring_total=hiring_total, facets=facets)
