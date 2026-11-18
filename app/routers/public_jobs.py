"""Router công khai cho Trang chủ & Trang tìm việc (tìm kiếm, lọc facets, công ty nổi bật, thống kê)."""
from datetime import datetime, timedelta, timezone
import math
import statistics

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import String, and_, cast, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_optional_user
from app.db.session import get_db
from app.models.application import Application
from app.models.company import Company
from app.models.job import (
    Job,
    MetaCategory,
    MetaLevel,
    MetaLocation,
    MetaSkill,
    MetaWorkType,
    SavedJob,
)
from app.models.user import User
from app.schemas.job import (
    FacetItemOut,
    FeaturedCompanyOut,
    HomeStatsOut,
    PublicJobCardOut,
    PublicJobsFacetsOut,
    PublicJobsSearchOut,
)
from app.services.matching import compute_job_match, normalize_skill_list

router = APIRouter(tags=["Public Jobs"])


def _split_csv(val: str) -> list[str]:
    return [x.strip() for x in val.split(",") if x.strip()]


def _build_filters(
    *,
    q: str = "",
    location: str = "",
    level: str = "",
    work_type: str = "",
    category: str = "",
    company_id: int | None = None,
    company: str = "",
    salary_min: int | None = None,
    salary_max: int | None = None,
    skills: str = "",
    exclude: str = "",
):
    conds = [Job.status == "published"]

    kw = q.strip()
    if kw:
        # Dùng FULLTEXT cho từ khóa >= 3 ký tự (tham số hóa hoàn toàn), fallback LIKE cho từ khóa ngắn
        tokens = [t for t in kw.replace("-", " ").split() if len(t) >= 2]
        if len(kw) >= 3 and tokens:
            boolean_q = " ".join(f"+{t}*" for t in tokens[:5])
            conds.append(
                or_(
                    text("MATCH(jobs.title) AGAINST(:ft_q IN BOOLEAN MODE)").bindparams(ft_q=boolean_q),
                    Job.title.ilike(f"%{kw}%"),
                )
            )
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


def _base_joined_query():
    return (
        select(Job)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
        .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
    )


def _fetch_market_benchmarks(db: Session) -> dict:
    """Tính 1 lần mức lương trung bình thị trường theo (category_id, level_id).

    Trả về dict: {(category_id, level_id): {"count": int, "avg_salary": float}}
    Dùng để tránh N+1 query khi dựng danh sách tin tuyển dụng.
    """
    stmt = (
        select(
            Job.category_id,
            Job.level_id,
            func.count(Job.id).label("cnt"),
            func.avg(
                (func.coalesce(Job.salary_min, Job.salary_max)
                 + func.coalesce(Job.salary_max, Job.salary_min)) / 2.0
            ).label("avg_sal"),
        )
        .where(
            Job.status == "published",
            (Job.salary_min.is_not(None) | Job.salary_max.is_not(None)),
        )
        .group_by(Job.category_id, Job.level_id)
    )
    out: dict = {}
    for row in db.execute(stmt).all():
        out[(row.category_id, row.level_id)] = {
            "count": int(row.cnt or 0),
            "avg_salary": float(row.avg_sal or 0),
        }
    return out


def _compute_facet(db: Session, model_cls, fk_col, filter_kwargs: dict, exclude_key: str) -> list[FacetItemOut]:
    conds = _build_filters(**filter_kwargs, exclude=exclude_key)
    subq = (
        select(
            fk_col.label("meta_id"),
            func.count(func.distinct(Job.id)).label("cnt"),
        )
        .select_from(Job)
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
        .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .where(*conds)
        .group_by(fk_col)
        .subquery()
    )
    stmt = (
        select(model_cls.slug, model_cls.name, func.coalesce(subq.c.cnt, 0).label("cnt"))
        .outerjoin(subq, model_cls.id == subq.c.meta_id)
        .order_by(text("cnt DESC"), model_cls.sort_order.asc(), model_cls.id.asc())
    )
    return [FacetItemOut(value=r.slug, label=r.name, count=int(r.cnt)) for r in db.execute(stmt).all()]


@router.get("/jobs", response_model=PublicJobsSearchOut, summary="Tìm kiếm việc làm công khai kèm facets")
def search_public_jobs(
    q: str = Query("", max_length=120),
    location: str = Query("", max_length=200),
    level: str = Query("", max_length=200),
    type: str = Query("", max_length=200),
    category: str = Query("", max_length=200),
    company_id: int | None = Query(None, ge=1),
    company: str = Query("", max_length=120),
    salary_min: int | None = Query(None, ge=0),
    salary_max: int | None = Query(None, ge=0),
    skills: str = Query("", max_length=300),
    sort: str = Query("newest", description="newest|salary_desc|relevant"),
    distinct_company: bool = Query(
        False,
        description="Chỉ lấy 1 việc mới nhất cho mỗi công ty (DISTINCT theo company_id)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    filter_kwargs = dict(
        q=q, location=location, level=level, work_type=type,
        category=category, company_id=company_id, company=company,
        salary_min=salary_min, salary_max=salary_max, skills=skills,
    )
    conds = _build_filters(**filter_kwargs)

    total = int(
        db.scalar(
            select(func.count(func.distinct(Job.id)))
            .select_from(Job)
            .outerjoin(Company, Job.company_id == Company.id)
            .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
            .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
            .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
            .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
            .where(*conds)
        ) or 0
    )
    # Ở chế độ DISTINCT theo công ty, "tổng số việc" = số công ty có tuyển.
    if distinct_company:
        total = int(
            db.scalar(
                select(func.count(func.distinct(Job.company_id)))
                .select_from(Job)
                .outerjoin(Company, Job.company_id == Company.id)
                .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
                .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
                .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
                .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
                .where(*conds)
            ) or 0
        )
    total_pages = max(1, math.ceil(total / page_size))
    safe_page = min(page, total_pages)
    offset = (safe_page - 1) * page_size

    if sort == "salary_desc":
        order_clauses = [func.coalesce(Job.salary_max, Job.salary_min, 0).desc(), Job.published_at.desc(), Job.id.desc()]
    elif sort == "relevant":
        order_clauses = [Job.views_count.desc(), Job.published_at.desc(), Job.id.desc()]
    else:
        order_clauses = [func.coalesce(Job.published_at, Job.created_at).desc(), Job.id.desc()]

    stmt = (
        select(
            Job,
            Company.name.label("company_name"),
            Company.slug.label("company_slug"),
            MetaLocation.slug.label("loc_slug"),
            MetaLevel.slug.label("lvl_slug"),
            MetaWorkType.slug.label("wt_slug"),
            MetaCategory.name.label("cat_name"),
            MetaCategory.slug.label("cat_slug"),
        )
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
        .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaWorkType, Job.work_type_id == MetaWorkType.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .where(*conds)
        .order_by(*order_clauses)
        .offset(offset)
        .limit(page_size)
    )
    # DISTINCT theo công ty: mỗi company_id chỉ xuất hiện 1 lần (việc mới nhất).
    # MySQL 8 dùng ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY published_at DESC).
    if distinct_company:
        ranked = (
            select(
                Job.id.label("jid"),
                func.row_number().over(
                    partition_by=Job.company_id,
                    order_by=[func.coalesce(Job.published_at, Job.created_at).desc(), Job.id.desc()],
                ).label("rn"),
            )
            .where(*conds)
            .subquery()
        )
        stmt = stmt.add_columns(ranked.c.rn).join(ranked, ranked.c.jid == Job.id).where(ranked.c.rn == 1)

    rows = db.execute(stmt).all()

    saved_ids: set[int] = set()
    cand_profile_data: dict | None = None
    if current_user and rows:
        job_ids = [r.Job.id for r in rows]
        saved_ids = set(
            db.scalars(
                select(SavedJob.job_id).where(
                    SavedJob.user_id == current_user.id,
                    SavedJob.job_id.in_(job_ids),
                )
            ).all()
        )
        # Lấy kỹ năng của ứng viên
        prof = db.execute(text("SELECT skills_json, level, location, work_type, expected_salary, headline FROM candidate_profiles WHERE user_id = :uid"), {"uid": current_user.id}).fetchone()
        cand_skills_list = []
        if prof and prof[0]:
            raw = prof[0]
            if isinstance(raw, list):
                cand_skills_list = [str(s).strip() for s in raw if str(s).strip()]
            elif isinstance(raw, str):
                try:
                    import json
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        cand_skills_list = [str(s).strip() for s in parsed if str(s).strip()]
                    else:
                        cand_skills_list = [s.strip() for s in str(parsed).split(",") if s.strip()]
                except Exception:
                    cand_skills_list = [s.strip() for s in raw.split(",") if s.strip()]
        if cand_skills_list:
            c_lvl = prof.level if prof and prof.level else None
            if not c_lvl and prof and prof.headline:
                hl = prof.headline.lower()
                c_lvl = next((k.title() for k in ("senior", "junior", "middle", "intern", "lead") if k in hl), None)
            cand_profile_data = {
                "skills": cand_skills_list,
                "level": c_lvl,
                "location": prof.location if prof else None,
                "work_type": prof.work_type if prof else None,
                "expected_salary": prof.expected_salary if prof else None,
            }

    items = []
    # Bảng cache benchmark lương theo (category_id, level_id).
    market_benchmarks = _fetch_market_benchmarks(db)

    for r in rows:
        job = r.Job
        clean_title = (job.title or "").replace("[Seed]", "").strip()

        # Tính điểm khớp (match score) chuẩn hóa
        match_score = None
        matched_sk = []
        missing_sk = []
        match_reason = None
        if cand_profile_data:
            j_skills = job.skills if isinstance(job.skills, list) else []
            j_dict = {
                "skills": j_skills, "level": job.level, "location": job.location,
                "work_type": job.work_type, "salary_min": job.salary_min, "salary_max": job.salary_max,
                "is_salary_negotiable": bool(job.is_salary_negotiable),
            }
            m_res = compute_job_match(cand_profile_data, j_dict)
            match_score = m_res["match_score"]
            matched_sk = m_res["matched_skills"]
            missing_sk = m_res["missing_skills"]
            match_reason = m_res["reason"]

        # So sánh lương với thị trường (nếu có category & level)
        salary_insight = None
        if job.salary_min or job.salary_max:
            job_avg = ((job.salary_min or job.salary_max) + (job.salary_max or job.salary_min)) // 2
            bench = market_benchmarks.get((job.category_id, job.level_id))
            if bench and bench["count"] >= 5 and bench["avg_salary"]:
                diff_pct = int(((job_avg - bench["avg_salary"]) / bench["avg_salary"]) * 100)
                if diff_pct >= 5:
                    salary_insight = f"Cao hơn thị trường {diff_pct}%"
                elif diff_pct <= -5:
                    salary_insight = f"Thấp hơn thị trường {abs(diff_pct)}%"

        items.append(
            PublicJobCardOut(
                id=job.id,
                title=clean_title,
                company_id=job.company_id,
                company_slug=r.company_slug,
                company_name=r.company_name or "Doanh nghiệp công nghệ",
                location=job.location,
                location_slug=r.loc_slug,
                level=job.level,
                level_slug=r.lvl_slug,
                work_type=job.work_type,
                work_type_slug=r.wt_slug,
                category=r.cat_name,
                category_slug=r.cat_slug,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                is_salary_negotiable=job.is_salary_negotiable,
                skills=list(job.skills or []),
                published_at=job.published_at,
                created_at=job.created_at,
                is_saved=job.id in saved_ids,
                match_score=match_score,
                matched_skills=matched_sk,
                missing_skills=missing_sk,
                salary_insight=salary_insight,
            )
        )

    facets = PublicJobsFacetsOut(
        location=_compute_facet(db, MetaLocation, Job.location_id, filter_kwargs, "location"),
        level=_compute_facet(db, MetaLevel, Job.level_id, filter_kwargs, "level"),
        type=_compute_facet(db, MetaWorkType, Job.work_type_id, filter_kwargs, "type"),
        category=_compute_facet(db, MetaCategory, Job.category_id, filter_kwargs, "category"),
    )

    return PublicJobsSearchOut(
        items=items,
        total=total,
        page=safe_page,
        page_size=page_size,
        total_pages=total_pages,
        facets=facets,
    )


@router.get("/companies/featured", response_model=list[FeaturedCompanyOut], summary="Công ty nổi bật theo số tin đang tuyển")
def list_featured_companies(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    stmt = (
        select(
            Company.id,
            Company.name,
            Company.slug,
            func.count(Job.id).label("job_count"),
        )
        .join(Job, and_(Job.company_id == Company.id, Job.status == "published"))
        .where(Company.is_draft == False)  # noqa: E712
        .group_by(Company.id, Company.slug)
        .having(func.count(Job.id) > 0)
        .order_by(func.count(Job.id).desc(), Company.id.asc())
        .limit(limit)
    )
    return [FeaturedCompanyOut(id=r.id, name=r.name, slug=r.slug, job_count=int(r.job_count)) for r in db.execute(stmt).all()]


@router.get("/stats/home", response_model=HomeStatsOut, summary="Thống kê thật cho trang chủ")
def get_home_stats(db: Session = Depends(get_db)):
    total_published = int(db.scalar(select(func.count(Job.id)).where(Job.status == "published")) or 0)
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = int(
        db.scalar(
            select(func.count(Job.id)).where(
                Job.status == "published",
                func.coalesce(Job.published_at, Job.created_at) >= today_start,
            )
        ) or 0
    )
    seven_days_ago = now_utc - timedelta(days=7)
    weekly_new = int(
        db.scalar(
            select(func.count(Job.id)).where(
                Job.status == "published",
                func.coalesce(Job.published_at, Job.created_at) >= seven_days_ago,
            )
        ) or 0
    )
    total_companies = int(
        db.scalar(select(func.count(Company.id)).where(Company.is_draft == False)) or 0  # noqa: E712
    )
    salary_rows = db.execute(select(Job.salary_min, Job.salary_max).where(Job.status == "published")).all()
    mids = [
        (s_min + s_max) / 2 if (s_min and s_max) else (s_min or s_max)
        for s_min, s_max in salary_rows
        if (s_min or s_max)
    ]
    median_sal = int(statistics.median(mids)) if mids else 0
    total_skills = int(db.scalar(select(func.count(MetaSkill.id))) or 0)

    return HomeStatsOut(
        total_published_jobs=total_published,
        today_new_jobs=today_new,
        total_companies=total_companies,
        weekly_new_jobs=weekly_new,
        salary_median=median_sal,
        total_skills=total_skills,
    )


@router.post("/jobs/{job_id}/save", summary="Lưu hoặc bỏ lưu việc làm (cần đăng nhập)")
def toggle_save_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(Job, job_id)
    if not job or job.status != "published":
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng")

    existing = db.scalar(
        select(SavedJob).where(SavedJob.user_id == current_user.id, SavedJob.job_id == job_id)
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"job_id": job_id, "is_saved": False, "message": "Đã bỏ lưu tin tuyển dụng"}

    db.add(SavedJob(user_id=current_user.id, job_id=job_id))
    db.commit()
    return {"job_id": job_id, "is_saved": True, "message": "Đã lưu tin tuyển dụng"}


@router.get("/jobs/{job_id}", summary="Chi tiết việc làm công khai")
def get_public_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    stmt = (
        select(
            Job,
            Company.name.label("company_name"),
            Company.slug.label("company_slug"),
            MetaCategory.name.label("category_name"),
            MetaCategory.slug.label("category_slug"),
        )
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .where(Job.id == job_id, Job.status == "published")
    )
    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin tuyển dụng")

    job = row.Job
    skills = job.skills if isinstance(job.skills, list) else []

    # Trạng thái cá nhân của khách (nếu đã đăng nhập):
    #   is_saved -> đã lưu tin hay chưa, applied -> đã ứng tuyển hay chưa.
    is_saved = False
    applied = False
    if user is not None:
        is_saved = db.scalar(
            select(SavedJob.id).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id)
        ) is not None
        applied = db.scalar(
            select(Application.id).where(
                Application.candidate_id == user.id,
                Application.job_id == job_id,
                Application.status.notin_(["withdrawn", "WITHDRAWN"]),
            )
        ) is not None

    return {
        "id": job.id,
        "title": (job.title or "").replace("[Seed] ", "").replace("[Seed]", ""),
        "company_id": job.company_id or job.employer_id,
        "company_slug": row.company_slug,
        "company_name": row.company_name or "Doanh nghiệp tuyển dụng",
        "company_logo": None,
        "location": job.location,
        "type": job.work_type if hasattr(job, "work_type") and job.work_type else "Toàn thời gian",
        "level": job.level or "Tất cả",
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "is_salary_negotiable": job.is_salary_negotiable,
        "description": job.description,
        "requirements": job.requirements,
        "benefits": "\n".join(job.benefits) if isinstance(job.benefits, list) else (job.benefits or ""),
        "skills": skills,
        "category_id": job.category_id,
        "category_name": row.category_name,
        "category_slug": row.category_slug,
        "quantity": job.quantity,
        "deadline": job.deadline,
        "created_at": job.created_at,
        "published_at": job.published_at,
        "is_saved": is_saved,
        "applied": applied,
    }


