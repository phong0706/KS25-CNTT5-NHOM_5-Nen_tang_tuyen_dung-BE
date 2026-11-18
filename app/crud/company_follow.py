"""Các truy vấn lưu trữ cho chức năng theo dõi công ty."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_follow import CompanyFollow
from app.models.job import Job, MetaCategory


def insert_follow(db: Session, candidate_id: int, company_id: int) -> bool:
    """Tạo quan hệ; unique constraint giải quyết an toàn các yêu cầu đồng thời."""
    db.add(CompanyFollow(candidate_id=candidate_id, company_id=company_id))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        if db.scalar(
            select(CompanyFollow.id).where(
                CompanyFollow.candidate_id == candidate_id,
                CompanyFollow.company_id == company_id,
            )
        ):
            return False
        raise


def delete_follow(db: Session, candidate_id: int, company_id: int) -> None:
    db.query(CompanyFollow).filter(
        CompanyFollow.candidate_id == candidate_id,
        CompanyFollow.company_id == company_id,
    ).delete(synchronize_session=False)
    db.commit()


def is_following(db: Session, candidate_id: int, company_id: int) -> bool:
    return db.scalar(
        select(CompanyFollow.id).where(
            CompanyFollow.candidate_id == candidate_id,
            CompanyFollow.company_id == company_id,
        )
    ) is not None


def count_followers(db: Session, company_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(CompanyFollow.id)).where(CompanyFollow.company_id == company_id)
        )
        or 0
    )


def list_followed_companies(
    db: Session,
    candidate_id: int,
    page: int,
    limit: int,
    keyword: str | None,
) -> tuple[list, int]:
    published_jobs = (
        select(Job.company_id, func.count(Job.id).label("job_count"))
        .where(Job.status == "published")
        .group_by(Job.company_id)
        .subquery()
    )
    industry_table = MetaCategory
    query = (
        select(
            CompanyFollow.created_at.label("followed_at"),
            Company.id,
            Company.name,
            Company.logo,
            Company.logo_url,
            Company.address,
            industry_table.name.label("industry_name"),
            func.coalesce(published_jobs.c.job_count, 0).label("job_count"),
        )
        .join(Company, Company.id == CompanyFollow.company_id)
        .outerjoin(industry_table, industry_table.id == Company.industry_id)
        .outerjoin(published_jobs, published_jobs.c.company_id == Company.id)
        .where(CompanyFollow.candidate_id == candidate_id)
    )
    if keyword:
        query = query.where(Company.name.ilike(f"%{keyword}%"))

    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.execute(
        query.order_by(CompanyFollow.created_at.desc(), CompanyFollow.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return rows, total
