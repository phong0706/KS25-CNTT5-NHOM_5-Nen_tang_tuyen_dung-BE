"""Nghiệp vụ theo dõi công ty."""
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import company_follow as repository
from app.models.company import Company, CompanyStatus

logger = logging.getLogger(__name__)


def follow_company(db: Session, candidate_id: int, company_id: int) -> bool:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Công ty không tồn tại.")
    if company.status != CompanyStatus.VERIFIED or company.is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể theo dõi công ty đang hoạt động.",
        )

    created = repository.insert_follow(db, candidate_id, company_id)
    logger.info(
        "company_follow candidate_id=%s company_id=%s created=%s",
        candidate_id,
        company_id,
        created,
    )
    return created


def unfollow_company(db: Session, candidate_id: int, company_id: int) -> None:
    repository.delete_follow(db, candidate_id, company_id)
    logger.info("company_unfollow candidate_id=%s company_id=%s", candidate_id, company_id)


def get_follow_status(db: Session, candidate_id: int | None, company_id: int) -> tuple[bool, int]:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Công ty không tồn tại.")
    following = bool(candidate_id and repository.is_following(db, candidate_id, company_id))
    return following, repository.count_followers(db, company_id)
