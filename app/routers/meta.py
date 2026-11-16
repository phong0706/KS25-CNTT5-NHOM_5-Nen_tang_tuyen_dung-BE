"""Router danh mục meta từ MySQL (locations, levels, work-types, categories, skills) kèm job_count."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job, MetaCategory, MetaLevel, MetaLocation, MetaSkill, MetaWorkType
from app.schemas.job import MetaCategoryOut, MetaOptionOut, MetaSkillOut

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get("/locations", response_model=list[MetaOptionOut], summary="Danh sách địa điểm kèm số tin")
def list_locations(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=300"
    stmt = (
        select(
            MetaLocation.id,
            MetaLocation.slug,
            MetaLocation.name,
            func.count(Job.id).label("job_count"),
        )
        .outerjoin(Job, and_(Job.location_id == MetaLocation.id, Job.status == "published"))
        .group_by(MetaLocation.id)
        .order_by(MetaLocation.sort_order.asc(), MetaLocation.id.asc())
    )
    return [MetaOptionOut(id=r.id, slug=r.slug, name=r.name, job_count=int(r.job_count)) for r in db.execute(stmt).all()]


@router.get("/levels", response_model=list[MetaOptionOut], summary="Danh sách cấp bậc kèm số tin")
def list_levels(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=300"
    stmt = (
        select(
            MetaLevel.id,
            MetaLevel.slug,
            MetaLevel.name,
            func.count(Job.id).label("job_count"),
        )
        .outerjoin(Job, and_(Job.level_id == MetaLevel.id, Job.status == "published"))
        .group_by(MetaLevel.id)
        .order_by(MetaLevel.sort_order.asc(), MetaLevel.id.asc())
    )
    return [MetaOptionOut(id=r.id, slug=r.slug, name=r.name, job_count=int(r.job_count)) for r in db.execute(stmt).all()]


@router.get("/work-types", response_model=list[MetaOptionOut], summary="Danh sách hình thức làm việc kèm số tin")
def list_work_types(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=300"
    stmt = (
        select(
            MetaWorkType.id,
            MetaWorkType.slug,
            MetaWorkType.name,
            func.count(Job.id).label("job_count"),
        )
        .outerjoin(Job, and_(Job.work_type_id == MetaWorkType.id, Job.status == "published"))
        .group_by(MetaWorkType.id)
        .order_by(MetaWorkType.sort_order.asc(), MetaWorkType.id.asc())
    )
    return [MetaOptionOut(id=r.id, slug=r.slug, name=r.name, job_count=int(r.job_count)) for r in db.execute(stmt).all()]


@router.get("/categories", response_model=list[MetaCategoryOut], summary="Danh sách ngành nghề kèm số tin")
def list_categories(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=300"
    stmt = (
        select(
            MetaCategory.id,
            MetaCategory.slug,
            MetaCategory.name,
            MetaCategory.icon,
            func.count(Job.id).label("job_count"),
        )
        .outerjoin(Job, and_(Job.category_id == MetaCategory.id, Job.status == "published"))
        .group_by(MetaCategory.id)
        .order_by(MetaCategory.sort_order.asc(), MetaCategory.id.asc())
    )
    return [
        MetaCategoryOut(id=r.id, slug=r.slug, name=r.name, icon=r.icon, job_count=int(r.job_count))
        for r in db.execute(stmt).all()
    ]


@router.get("/skills", response_model=list[MetaSkillOut], summary="Gợi ý kỹ năng (tối đa 10)")
def search_skills(
    q: str = Query("", max_length=80),
    db: Session = Depends(get_db),
):
    stmt = select(MetaSkill)
    keyword = q.strip()
    if keyword:
        stmt = stmt.where(MetaSkill.name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(MetaSkill.usage_count.desc(), MetaSkill.name.asc()).limit(10)
    rows = db.scalars(stmt).all()
    return [
        MetaSkillOut(id=s.id, name=s.name, usage_count=s.usage_count, job_count=s.usage_count)
        for s in rows
    ]
