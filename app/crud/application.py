"""CRUD operations cho Application (đơn ứng tuyển)."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.models.application_status_history import ApplicationStatusHistory
from app.schemas.application_schema import ApplicationCreate


def get_application_by_id(db: Session, application_id: int) -> Application | None:
    """Lấy đơn ứng tuyển theo ID."""
    return db.get(Application, application_id)


def check_duplicate_application(
    db: Session, candidate_profile_id: int, job_id: int
) -> Application | None:
    """Kiểm tra đơn ứng tuyển đã tồn tại chưa (dựa trên UNIQUE constraint)."""
    query = select(Application).where(
        Application.candidate_profile_id == candidate_profile_id,
        Application.job_id == job_id,
    )
    return db.scalar(query)


def create_application(
    db: Session, candidate_profile_id: int, data: ApplicationCreate
) -> Application:
    """Tạo đơn ứng tuyển mới.
    
    Tự động tạo bản ghi lịch sử trạng thái đầu tiên (SUBMITTED).
    
    Raises:
        IntegrityError: Nếu đã tồn tại đơn ứng tuyển (UNIQUE constraint violation)
    """
    # Tạo application với trạng thái SUBMITTED
    application = Application(
        candidate_profile_id=candidate_profile_id,
        job_id=data.job_id,
        cv_id=data.cv_id,
        cover_letter=data.cover_letter,
        status=ApplicationStatus.SUBMITTED,
    )
    
    try:
        db.add(application)
        db.flush()  # Để lấy application.id trước khi commit
        
        # Tạo bản ghi lịch sử trạng thái đầu tiên
        history = ApplicationStatusHistory(
            application_id=application.id,
            old_status=None,  # Lần đầu không có trạng thái cũ
            new_status=ApplicationStatus.SUBMITTED.value,
            changed_by_user_id=None,  # Ứng viên tự nộp, không có changed_by
        )
        db.add(history)
        
        db.commit()
        db.refresh(application)
        return application
        
    except IntegrityError as e:
        db.rollback()
        # Re-raise để router xử lý và trả HTTP 409
        raise e


def get_applications_by_candidate(
    db: Session, candidate_profile_id: int
) -> list[Application]:
    """Lấy danh sách đơn ứng tuyển của một ứng viên."""
    query = (
        select(Application)
        .where(Application.candidate_profile_id == candidate_profile_id)
        .order_by(Application.created_at.desc())
    )
    return list(db.scalars(query))


def get_applications_by_job(db: Session, job_id: int) -> list[Application]:
    """Lấy danh sách đơn ứng tuyển cho một tin tuyển dụng."""
    query = (
        select(Application)
        .where(Application.job_id == job_id)
        .order_by(Application.created_at.desc())
    )
    return list(db.scalars(query))
