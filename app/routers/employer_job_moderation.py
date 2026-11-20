"""Router gửi duyệt và thu hồi tin tuyển dụng cho Nhà tuyển dụng."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.user import User
from app.schemas.job_moderation import JobModerationActionIn, JobModerationOut
from app.services.job_moderation_service import (
    submit_job_for_review_service,
    withdraw_job_to_draft_service,
)

router = APIRouter(prefix="/employer/jobs", tags=["Employer Job Moderation"])


@router.post("/{job_id}/submit", response_model=JobModerationOut)
def employer_submit_job(
    job_id: int,
    payload: JobModerationActionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    """Nhà tuyển dụng gửi duyệt tin tuyển dụng (draft/rejected -> pending)."""
    return submit_job_for_review_service(
        db=db,
        job_id=job_id,
        employer_id=current_user.id,
        expected_version=payload.version,
    )


@router.post("/{job_id}/withdraw", response_model=JobModerationOut)
def employer_withdraw_job(
    job_id: int,
    payload: JobModerationActionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer")),
):
    """Nhà tuyển dụng rút tin chờ duyệt về nháp (pending -> draft)."""
    return withdraw_job_to_draft_service(
        db=db,
        job_id=job_id,
        employer_id=current_user.id,
        expected_version=payload.version,
    )
