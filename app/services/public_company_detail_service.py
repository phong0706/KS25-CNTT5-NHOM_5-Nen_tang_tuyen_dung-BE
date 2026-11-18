"""Dịch vụ chi tiết Công ty & Việc làm đang tuyển (/api/companies/{slug} và /{slug}/jobs)."""
from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job, MetaCategory, MetaLevel, MetaLocation, SavedJob
from app.models.user import User
from app.schemas.company import (
    CompanyDetailSalaryOut, CompanyFacetItemOut, CompanyIndustryOut,
    CompanyJobsFacetsOut, PublicCompanyDetailOut, PublicCompanyJobsOut,
)
from app.schemas.job import PublicJobCardOut
from app.services.public_company_rules import slugify_skill
from app.services.public_company_service import (
    build_company_card, extract_top_skills_by_company, job_agg_subquery, open_job_conds, safe_media, safe_site,
)


def get_public_company_detail(db: Session, slug: str) -> PublicCompanyDetailOut:
    row = db.execute(
        select(Company, MetaCategory.slug.label("ind_slug"), MetaCategory.name.label("ind_name"), MetaLocation.name.label("loc_name"))
        .outerjoin(MetaCategory, Company.industry_id == MetaCategory.id)
        .outerjoin(MetaLocation, Company.location_id == MetaLocation.id)
        .where(Company.slug == slug, Company.is_visible == True, Company.is_draft == False)  # noqa: E712
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty")

    c, ind_slug, ind_name, loc_name = row[0], row.ind_slug, row.ind_name, row.loc_name
    agg_sub = job_agg_subquery()
    agg_row = db.execute(select(agg_sub).where(agg_sub.c.company_id == c.id)).first()
    open_jobs = int(agg_row.open_jobs or 0) if agg_row else 0
    sal_range = None
    if agg_row and int(agg_row.salary_sample_size or 0) >= 2 and agg_row.min_salary is not None and agg_row.max_salary is not None:
        sal_range = CompanyDetailSalaryOut(min=int(agg_row.min_salary), max=int(agg_row.max_salary), sample_size=int(agg_row.salary_sample_size))

    skills_map = extract_top_skills_by_company(db, [c.id], 8)
    sim_rows = []
    if c.industry_id:
        agg2 = job_agg_subquery()
        sim_rows = db.execute(
            select(Company, MetaCategory.slug.label("ind_slug"), MetaCategory.name.label("ind_name"), MetaLocation.name.label("loc_name"), agg2)
            .outerjoin(MetaCategory, Company.industry_id == MetaCategory.id)
            .outerjoin(MetaLocation, Company.location_id == MetaLocation.id)
            .join(agg2, and_(Company.id == agg2.c.company_id, agg2.c.open_jobs > 0))
            .where(Company.is_visible == True, Company.is_draft == False, Company.industry_id == c.industry_id, Company.id != c.id)  # noqa: E712
            .order_by(agg2.c.open_jobs.desc(), Company.name.asc())
            .limit(3)
        ).all()
    sim_skills = extract_top_skills_by_company(db, [r[0].id for r in sim_rows], 3)
    similar = [build_company_card(r[0], r.ind_slug, r.ind_name, r.loc_name, r, [s.name for s in sim_skills.get(r[0].id, [])]) for r in sim_rows]

    return PublicCompanyDetailOut(
        slug=c.slug or str(c.id), name=c.name, tagline=c.tagline, description=c.description,
        logo_url=safe_media(c.logo_url if c.logo_status != "removed" else None),
        cover_url=safe_media(c.cover_url),
        industry=CompanyIndustryOut(slug=ind_slug, name=ind_name) if ind_slug and ind_name else None,
        location=loc_name or c.address, address=c.address, size_range=c.size_range, founded_year=c.founded_year,
        website=safe_site(c.website), is_verified=bool(c.is_verified), updated_at=c.updated_at,
        open_jobs=open_jobs, salary_range=sal_range, latest_job_at=agg_row.latest_job_at if agg_row else None,
        top_skills=skills_map.get(c.id, []), similar=similar,
    )


def list_public_company_jobs(
    db: Session, slug: str, *, sort: str, location: str, level: str, page: int, page_size: int, current_user: User | None
) -> PublicCompanyJobsOut:
    c = db.scalar(select(Company).where(Company.slug == slug, Company.is_visible == True, Company.is_draft == False))  # noqa: E712
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty")

    loc_slug_map = {r.name: r.slug for r in db.execute(select(MetaLocation.slug, MetaLocation.name)).all()}
    lvl_slug_map = {r.name: r.slug for r in db.execute(select(MetaLevel.slug, MetaLevel.name)).all()}
    conds = open_job_conds(c.id)
    if location:
        loc_name = next((n for n, s in loc_slug_map.items() if s == location), location)
        conds.append(Job.location == loc_name)
    if level:
        lvl_name = next((n for n, s in lvl_slug_map.items() if s == level), level)
        conds.append(Job.level == lvl_name)

    total = int(db.scalar(select(func.count(Job.id)).where(*conds)) or 0)
    order = [case((Job.is_salary_negotiable == True, 1), else_=0).asc(), func.coalesce(Job.salary_max, Job.salary_min, 0).desc(), Job.id.desc()] if sort == "salary" else [func.coalesce(Job.published_at, Job.created_at).desc(), Job.id.desc()]  # noqa: E712
    jobs = db.scalars(select(Job).where(*conds).order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()

    saved_ids = set(db.scalars(select(SavedJob.job_id).where(SavedJob.user_id == current_user.id, SavedJob.job_id.in_([j.id for j in jobs]))).all()) if (current_user and jobs) else set()
    items = [
        PublicJobCardOut(
            id=j.id, title=j.title, company_id=c.id, company_slug=c.slug, company_name=c.name, location=j.location,
            location_slug=loc_slug_map.get(j.location or ""), level=j.level, level_slug=lvl_slug_map.get(j.level or ""),
            work_type=j.work_type, salary_min=j.salary_min, salary_max=j.salary_max,
            is_salary_negotiable=bool(j.is_salary_negotiable), skills=j.skills if isinstance(j.skills, list) else [],
            published_at=j.published_at, created_at=j.created_at, is_saved=j.id in saved_ids, is_expired=False, deadline=j.deadline,
        ) for j in jobs
    ]

    base_conds = open_job_conds(c.id)
    loc_cnt = db.execute(select(Job.location, func.count(Job.id)).where(*base_conds, Job.location.is_not(None)).group_by(Job.location)).all()
    lvl_cnt = db.execute(select(Job.level, func.count(Job.id)).where(*base_conds, Job.level.is_not(None)).group_by(Job.level)).all()
    return PublicCompanyJobsOut(
        items=items, total=total, page=page, page_size=page_size,
        facets=CompanyJobsFacetsOut(
            location=[CompanyFacetItemOut(value=loc_slug_map.get(n, slugify_skill(n)), label=n, count=int(cnt)) for n, cnt in loc_cnt],
            level=[CompanyFacetItemOut(value=lvl_slug_map.get(n, slugify_skill(n)), label=n, count=int(cnt)) for n, cnt in lvl_cnt],
        ),
    )
