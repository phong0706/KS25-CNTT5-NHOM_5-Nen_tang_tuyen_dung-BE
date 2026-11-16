"""Router phân tích & tra cứu mức lương IT (/api/salary/insights).
Dữ liệu tính từ tin tuyển dụng published có khai lương trong DB.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job, MetaCategory, MetaLocation, MetaLevel
from app.services.salary_stats import compute_salary_insights

router = APIRouter(prefix="/salary", tags=["Salary Insights"])

# Tỷ giá USD -> VND dùng để chuẩn hoá mức lương.
USD_EXCHANGE_RATE = 25400

# Ngưỡng nhận diện mức lương khai báo bằng USD.
# Mức lương IT bằng VND luôn >= 1.000.000; con số <= ngưỡng này chắc chắn là USD.
USD_THRESHOLD = 1_000_000


class RelaxedSuggestion(BaseModel):
    remove_param: str
    message: str
    available_samples: int


class LevelExpBenchmark(BaseModel):
    level_slug: str
    level_name: str
    exp_range: str
    median_salary: int
    sample_count: int


class SalaryInsightsOut(BaseModel):
    category: Optional[str] = None
    category_name: Optional[str] = None
    level: Optional[str] = None
    level_name: Optional[str] = None
    location: Optional[str] = None
    location_name: Optional[str] = None
    sample_size: int
    effective_sample_size: int
    min: int
    p25: int
    median: int
    p75: int
    max: int
    outliers_removed: int
    is_sufficient: bool
    updated_at: str
    currency_normalized: bool = True
    suggestions: List[RelaxedSuggestion] = []
    level_benchmarks: List[LevelExpBenchmark] = []


def _normalize_val(val: Optional[float]) -> Optional[float]:
    """Chuẩn hoá mức lương về VNĐ.

    Bản cũ dùng ngưỡng 10.000 nên mọi mức lương VND <= 10.000 bị nhân nhầm
    lên thành USD. Ngưỡng mới 1.000.000 an toàn cho mức lương IT (tối thiểu
    khoảng 3.000.000 VND/tháng) trong khi vẫn bắt được các mức USD (thường
    500 - 5.000 USD).
    """
    if not val:
        return None
    v = float(val)
    if v <= 0:
        return None
    if v <= USD_THRESHOLD:  # Định dạng USD
        return v * USD_EXCHANGE_RATE
    return v


def _fetch_salaries(db: Session, cat_slug: Optional[str] = None, lvl_slug: Optional[str] = None, loc_slug: Optional[str] = None):
    stmt = (
        select(Job.salary_min, Job.salary_max, func.coalesce(Job.published_at, Job.created_at).label("pub_time"))
        .outerjoin(MetaCategory, Job.category_id == MetaCategory.id)
        .outerjoin(MetaLevel, Job.level_id == MetaLevel.id)
        .outerjoin(MetaLocation, Job.location_id == MetaLocation.id)
        .where(Job.status == "published", Job.is_salary_negotiable == False, (Job.salary_min.is_not(None) | Job.salary_max.is_not(None)))
    )
    if cat_slug: stmt = stmt.where(MetaCategory.slug == cat_slug)
    if lvl_slug: stmt = stmt.where(MetaLevel.slug == lvl_slug)
    if loc_slug: stmt = stmt.where(MetaLocation.slug == loc_slug)

    rows = db.execute(stmt).all()
    salaries = []
    latest_time = None
    for r in rows:
        min_v = _normalize_val(r.salary_min)
        max_v = _normalize_val(r.salary_max)
        if min_v and max_v: salaries.append((min_v + max_v) / 2.0)
        elif min_v: salaries.append(min_v)
        elif max_v: salaries.append(max_v)
        if r.pub_time and (not latest_time or r.pub_time > latest_time):
            latest_time = r.pub_time
    return salaries, latest_time


EXP_MAPPING = {
    "fresher": "0 - 1 năm kinh nghiệm",
    "junior": "1 - 2 năm kinh nghiệm",
    "middle": "2 - 4 năm kinh nghiệm",
    "senior": "4 - 6 năm kinh nghiệm",
    "lead-manager": "Trên 6 năm kinh nghiệm",
}


def _get_level_benchmarks(db: Session, cat_slug: Optional[str] = None) -> List[LevelExpBenchmark]:
    levels = db.execute(select(MetaLevel).where(MetaLevel.slug.in_(list(EXP_MAPPING.keys()))).order_by(MetaLevel.sort_order.asc())).scalars().all()
    out = []
    for lvl in levels:
        sals, _ = _fetch_salaries(db, cat_slug, lvl.slug, None)
        if len(sals) >= 2:
            st = compute_salary_insights(sals)
            out.append(LevelExpBenchmark(level_slug=lvl.slug, level_name=lvl.name, exp_range=EXP_MAPPING.get(lvl.slug, ""), median_salary=st["median"], sample_count=len(sals)))
    return out


@router.get("/insights", response_model=SalaryInsightsOut, summary="Thống kê mức lương thị trường theo phân vị")
def get_salary_insights(
    response: Response,
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "public, max-age=120"
    cat_name = db.scalar(select(MetaCategory.name).where(MetaCategory.slug == category)) if category else None
    lvl_name = db.scalar(select(MetaLevel.name).where(MetaLevel.slug == level)) if level else None
    loc_name = db.scalar(select(MetaLocation.name).where(MetaLocation.slug == location)) if location else None

    salaries, latest_time = _fetch_salaries(db, category, level, location)
    stats = compute_salary_insights(salaries)
    up_date_str = latest_time.strftime("%d/%m/%Y") if latest_time else datetime.now().strftime("%d/%m/%Y")

    suggestions = []
    if not stats["is_sufficient"]:
        if location:
            rel_sal, _ = _fetch_salaries(db, category, level, None)
            if len(rel_sal) >= 5:
                suggestions.append(RelaxedSuggestion(remove_param="location", message=f"Bỏ lọc địa điểm sẽ có {len(rel_sal)} tin để thống kê", available_samples=len(rel_sal)))
        if level:
            rel_sal, _ = _fetch_salaries(db, category, None, location)
            if len(rel_sal) >= 5:
                suggestions.append(RelaxedSuggestion(remove_param="level", message=f"Bỏ lọc cấp bậc sẽ có {len(rel_sal)} tin để thống kê", available_samples=len(rel_sal)))
        if (location or level) and category:
            rel_sal, _ = _fetch_salaries(db, category, None, None)
            if len(rel_sal) >= 5 and not any(s.remove_param == "location" for s in suggestions):
                suggestions.append(RelaxedSuggestion(remove_param="level_and_location", message=f"Xem toàn bộ ngành '{cat_name or category}' có {len(rel_sal)} tin", available_samples=len(rel_sal)))

    benchmarks = _get_level_benchmarks(db, category)

    return SalaryInsightsOut(
        category=category, category_name=cat_name, level=level, level_name=lvl_name,
        location=location, location_name=loc_name, sample_size=stats["sample_size"],
        effective_sample_size=stats["effective_sample_size"] if stats["sample_size"] > 0 else 0,
        min=stats["min"], p25=stats["p25"], median=stats["median"], p75=stats["p75"], max=stats["max"],
        outliers_removed=stats["outliers_removed"], is_sufficient=stats["is_sufficient"],
        updated_at=up_date_str, currency_normalized=True, suggestions=suggestions, level_benchmarks=benchmarks,
    )
