"""CRUD operations cho Application (đơn ứng tuyển)."""
import math
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.models.application_status_history import ApplicationStatusHistory
from app.models.company import Company
from app.models.job import Job
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


def get_applications_by_candidate_paginated(
    db: Session,
    candidate_profile_id: int,
    *,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
) -> dict:
    """Lấy danh sách đơn ứng tuyển của ứng viên kèm phân trang và lọc trạng thái.

    Trả về dict: {items, total, page, page_size, total_pages}
    Mỗi item có kèm `job_title` và `company_name` để FE hiển thị.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    conditions = [Application.candidate_profile_id == candidate_profile_id]
    if status:
        conditions.append(Application.status == status)

    base = (
        select(
            Application,
            Job.title.label("job_title"),
            Company.name.label("company_name"),
        )
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Job.company_id)
        .where(*conditions)
    )

    total = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(*conditions)
    ) or 0

    rows = db.execute(
        base.order_by(Application.created_at.desc(), Application.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    items = []
    for row in rows:
        application = row[0]
        item = {
            "id": application.id,
            "candidate_profile_id": application.candidate_profile_id,
            "job_id": application.job_id,
            "job_title": row.job_title,
            "company_name": row.company_name,
            "status": application.status,
            "cv_id": application.cv_id,
            "cover_letter": application.cover_letter,
            "created_at": application.created_at,
            "updated_at": application.updated_at,
        }
        items.append(item)

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_applications_by_job(db: Session, job_id: int) -> list[Application]:
    """Lấy danh sách đơn ứng tuyển cho một tin tuyển dụng."""
    query = (
        select(Application)
        .where(Application.job_id == job_id)
        .order_by(Application.created_at.desc())
    )
    return list(db.scalars(query))


def get_status_history_by_application(
    db: Session, application_id: int
) -> list[ApplicationStatusHistory]:
    """Lấy lịch sử trạng thái của một đơn ứng tuyển, sắp xếp thời gian tăng dần."""
    query = (
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(
            ApplicationStatusHistory.changed_at.asc(),
            ApplicationStatusHistory.id.asc(),
        )
    )
    return list(db.scalars(query))


# Trạng thái không được phép rút đơn (đã có kết quả từ nhà tuyển dụng)
NON_WITHDRAWABLE_STATUSES = {
    ApplicationStatus.OFFERED,
    ApplicationStatus.REJECTED,
}

class WithdrawError(Exception):
    """Lỗi khi rút đơn ứng tuyển. Router chuyển thành HTTP error."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class WithdrawNotAllowedError(WithdrawError):
    """Đơn ở trạng thái không được phép rút (OFFERED / REJECTED / đã WITHDRAWN)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class WithdrawConflictError(WithdrawError):
    """Trạng thái đơn bị thay đổi bởi thao tác khác (cập nhật đồng thời)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)




def withdraw_application(
    db: Session,
    application: Application,
    *,
    user_id: int | None = None,
) -> tuple[Application, ApplicationStatusHistory | None]:
    """Rút đơn ứng tuyển: chuyển sang WITHDRAWN và ghi lịch sử trạng thái.

    - Không xoá hồ sơ, chỉ đổi trạng thái.
    - Cập nhật + ghi lịch sử trong **cùng một transaction** (một lần commit).
    - Chống cập nhật đồng thời: dùng `UPDATE ... WHERE status = <old>` để
      chỉ 1 request thắng; request còn lại thấy row_count=0 → báo lỗi 409.
    - Rút lại (đã WITHDRAWN) không ghi thêm lịch sử trùng.
    """
    old_status = application.status

    # Đã rút rồi → không ghi thêm lịch sử trùng
    if old_status == ApplicationStatus.WITHDRAWN:
        raise WithdrawNotAllowedError(
            "Đơn ứng tuyển này đã được rút trước đó."
        )

    # Chặn rút khi đã có kết quả
    if old_status in NON_WITHDRAWABLE_STATUSES:
        raise WithdrawNotAllowedError(
            f"Không thể rút đơn ở trạng thái {old_status.value}. "
            "Hồ sơ đã có kết quả từ nhà tuyển dụng."
        )

    # Update có điều kiện → chống race condition khi 2 request cùng lúc rút
    result = db.execute(
        update(Application)
        .where(
            Application.id == application.id,
            Application.status == old_status,
        )
        .values(status=ApplicationStatus.WITHDRAWN)
        .execution_options(synchronize_session=False)
    )

    if result.rowcount == 0:
        # Trạng thái đã bị request khác đổi trước đó → rollback phần đọc
        db.rollback()
        raise WithdrawConflictError(
            "Trạng thái đơn ứng tuyển vừa được thay đổi bởi thao tác khác. "
            "Vui lòng tải lại và thử lại."
        )

    # Ghi lịch sử trạng thái trong cùng transaction
    history = ApplicationStatusHistory(
        application_id=application.id,
        old_status=old_status.value,
        new_status=ApplicationStatus.WITHDRAWN.value,
        changed_by_user_id=user_id,
    )
    db.add(history)

    db.commit()
    db.refresh(application)
    db.refresh(history)
    return application, history
