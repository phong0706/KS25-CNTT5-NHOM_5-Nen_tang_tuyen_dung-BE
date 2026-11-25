"""CRUD operations cho Notification (thông báo)."""
from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    related_url: str | None = None,
) -> Notification | None:
    """Tạo thông báo mới qua service chuẩn (thay cho insert trực tiếp)."""
    from app.services.notification import create_notification as svc_create_notif
    return svc_create_notif(
        db=db,
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        link=related_url,
        commit=True,
    )


def notify_new_application(
    db: Session,
    employer_user_id: int,
    job_title: str,
    candidate_name: str,
    application_id: int,
) -> Notification:
    """Gửi thông báo cho nhà tuyển dụng khi có đơn ứng tuyển mới.
    
    Args:
        db: Database session
        employer_user_id: ID của nhà tuyển dụng (user_id)
        job_title: Tên tin tuyển dụng
        candidate_name: Tên ứng viên
        application_id: ID của đơn ứng tuyển
    
    Returns:
        Notification object vừa tạo
    """
    return create_notification(
        db=db,
        user_id=employer_user_id,
        notification_type="NEW_APPLICATION",
        title="Đơn ứng tuyển mới",
        message=f"{candidate_name} đã nộp đơn ứng tuyển vào vị trí '{job_title}'",
        related_url=f"/applications/{application_id}",
    )
