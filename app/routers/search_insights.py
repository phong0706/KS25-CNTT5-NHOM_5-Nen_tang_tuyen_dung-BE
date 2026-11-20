"""Router tiện ích tìm kiếm thông minh: gợi ý search, quick filters, saved searches & relaxed search."""
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select, text
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.application import SavedSearch
from app.models.company import Company
from app.models.job import Job, MetaCategory

router = APIRouter(tags=["Smart Search & Insights"])

# 1. Quick Filters
class QuickFilterItem(BaseModel):
    id: str
    label: str
    params: Dict[str, Any]

@router.get("/api/meta/quick-filters", response_model=List[QuickFilterItem], summary="Danh sách chip lọc nhanh động")
def get_quick_filters():
    return [
        QuickFilterItem(id="remote", label="Làm việc từ xa (Remote)", params={"type": "remote"}),
        QuickFilterItem(id="hybrid", label="Mô hình Hybrid", params={"type": "hybrid"}),
        QuickFilterItem(id="salary_30", label="Lương > 30 Triệu", params={"salary_min": 30000000}),
        QuickFilterItem(id="senior", label="Cấp bậc Senior", params={"level": "senior"}),
        QuickFilterItem(id="fresher", label="Fresher / Mới tốt nghiệp", params={"level": "fresher"}),
    ]

# 2. Gợi ý khi gõ (/api/search/suggest?q=...)
@router.get("/api/search/suggest", summary="Gợi ý tìm kiếm tức thì theo Vị trí / Kỹ năng / Công ty")
def get_search_suggestions(q: str = Query("", min_length=1, max_length=100), db: Session = Depends(get_db)):
    kw = q.strip().lower()
    if not kw:
        return {"items": []}

    results = []

    # Gợi ý vị trí công việc từ jobs (distinct title)
    title_rows = db.execute(
        text("SELECT DISTINCT title, COUNT(*) as cnt FROM jobs WHERE status = 'published' AND LOWER(title) LIKE :kw GROUP BY title ORDER BY cnt DESC LIMIT 4"),
        {"kw": f"%{kw}%"}
    ).fetchall()
    for r in title_rows:
        results.append({"type": "position", "group": "Vị trí", "text": r.title, "count": r.cnt})

    # Gợi ý công ty từ companies
    comp_rows = db.execute(
        text("SELECT DISTINCT name FROM companies WHERE LOWER(name) LIKE :kw LIMIT 2"),
        {"kw": f"%{kw}%"}
    ).fetchall()
    for r in comp_rows:
        results.append({"type": "company", "group": "Công ty", "text": r.name, "count": None})

    # Gợi ý kỹ năng từ meta_skills
    skill_rows = db.execute(
        text("SELECT DISTINCT name FROM meta_skills WHERE LOWER(name) LIKE :kw LIMIT 2"),
        {"kw": f"%{kw}%"}
    ).fetchall()
    for r in skill_rows:
        results.append({"type": "skill", "group": "Kỹ năng", "text": r.name, "count": None})

    return {"items": results[:8]}

# 3. Gợi ý nới lỏng bộ lọc khi kết quả ít — xem endpoint bên dưới (đặt sau phần này
#    để thứ tự route không bị đảo).

@router.get("/api/jobs/relaxed", summary="Gợi ý nới lỏng bộ lọc thông minh")
def get_relaxed_search(
    q: Optional[str] = Query(""),
    location: Optional[str] = Query(""),
    level: Optional[str] = Query(""),
    category: Optional[str] = Query(""),
    type: Optional[str] = Query(""),
    salary_min: Optional[int] = Query(None, ge=0),
    salary_max: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db)
):
    """Gợi ý nới lỏng từng bộ lọc, CHỈ khi bỏ bộ lọc đó thực sự tăng số kết quả.

    Bản cũ chỉ đếm tổng số tin published rồi gợi ý "bỏ lọc địa điểm" — hoàn toàn
    không dựa trên bộ lọc đang dùng, nên gợi ý luôn vô nghĩa.

    LƯU Ý: endpoint này phải nằm TRƯỚC route "/jobs/{job_id}" của router public_jobs,
    nếu không FastAPI sẽ hiểu "relaxed" là job_id và trả 422.
    """
    def _count(**filters) -> int:
        stmt = (
            select(func.count(func.distinct(Job.id)))
            .join(Company, Job.company_id == Company.id)
            .where(
                Job.status == "published",
                Company.is_visible == True,  # noqa: E712
                or_(Job.deadline.is_(None), Job.deadline >= date.today()),
            )
        )
        if filters.get("q"):
            stmt = stmt.where(Job.title.ilike(f"%{filters['q']}%"))
        # location / level / work_type lưu dạng chuỗi trực tiếp trên bảng jobs.
        for key, col in (("location", Job.location), ("level", Job.level), ("type", Job.work_type)):
            raw = filters.get(key)
            if raw:
                vals = [v.strip() for v in raw.split(",") if v.strip()]
                if vals:
                    stmt = stmt.where(col.in_(vals))
        # category là khóa ngoại (category_id) -> phải join meta_categories để lọc theo slug/tên.
        raw_cat = filters.get("category")
        if raw_cat:
            vals = [v.strip() for v in raw_cat.split(",") if v.strip()]
            if vals:
                stmt = stmt.outerjoin(MetaCategory, Job.category_id == MetaCategory.id).where(
                    or_(MetaCategory.slug.in_(vals), MetaCategory.name.in_(vals))
                )
        if filters.get("salary_min") is not None:
            stmt = stmt.where(or_(Job.salary_max >= filters["salary_min"], Job.salary_min >= filters["salary_min"]))
        if filters.get("salary_max") is not None:
            stmt = stmt.where(or_(Job.salary_min <= filters["salary_max"], Job.salary_max <= filters["salary_max"]))
        return int(db.scalar(stmt) or 0)

    base = dict(
        q=q or "", location=location or "", level=level or "",
        category=category or "", type=type or "",
        salary_min=salary_min, salary_max=salary_max,
    )
    current_total = _count(**base)

    suggestions = []
    # Thử bỏ từng bộ lọc một; chỉ gợi ý nếu số kết quả tăng lên.
    removable = [
        ("location", "địa điểm", {"location": ""}),
        ("level", "cấp bậc", {"level": ""}),
        ("category", "ngành nghề", {"category": ""}),
        ("type", "hình thức làm việc", {"type": ""}),
        ("salary", "mức lương", {"salary_min": None, "salary_max": None}),
    ]
    for remove_param, label, override in removable:
        # Bỏ qua nếu bộ lọc đó đang trống rỗng
        if all(not base.get(k) for k in override):
            continue
        relaxed_total = _count(**{**base, **override})
        if relaxed_total > current_total:
            suggestions.append({
                "message": f"Bỏ bộ lọc {label} sẽ có {relaxed_total} việc làm (hiện tại {current_total})",
                "remove_param": remove_param,
            })

    return {"suggestions": suggestions, "current_total": current_total}


# 4. Lưu tìm kiếm (Saved Searches)
class SaveSearchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    filters: Dict[str, Any] = Field(default_factory=dict)

@router.get("/api/candidate/saved-searches", summary="Lấy danh sách tìm kiếm đã lưu của ứng viên")
def list_saved_searches(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    rows = db.scalars(
        select(SavedSearch)
        .where(SavedSearch.user_id == current_user.id)
        .order_by(SavedSearch.id.desc())
    ).all()

    items = []
    for r in rows:
        filters = r.filters_json
        if isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except (ValueError, TypeError):
                filters = {}
        items.append({
            "id": r.id,
            "name": r.name,
            "filters": filters or {},
            "new_jobs_count": 0,
            "created_at": str(r.created_at)
        })
    return items

@router.post("/api/candidate/saved-searches", summary="Lưu bộ lọc tìm kiếm hiện tại")
def create_saved_search(data: SaveSearchRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tên tìm kiếm không được để trống")

    row = SavedSearch(
        user_id=current_user.id,
        name=name,
        filters_json=json.dumps(data.filters or {}, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "message": "Đã lưu tìm kiếm thành công!"}

@router.delete("/api/candidate/saved-searches/{id}", summary="Xoá tìm kiếm đã lưu")
def delete_saved_search(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    row = db.scalar(select(SavedSearch).where(SavedSearch.id == id, SavedSearch.user_id == current_user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tìm kiếm đã lưu")
    db.delete(row)
    db.commit()
    return {"status": "ok", "message": "Đã xóa tìm kiếm đã lưu"}
