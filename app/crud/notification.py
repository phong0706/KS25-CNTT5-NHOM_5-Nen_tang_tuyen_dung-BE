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
) -> Notification:
    """Tạo thông báo mới cho người dùng.
    
    Args:
        db: Database session
        user_id: ID của người nhận thông báo
        notification_type: Loại thông báo (VD: "NEW_APPLICATION", "STATUS_CHANGE")
        title: Tiêu đề thông báo
        message: Nội dung chi tiết
        related_url: Link liên quan (optional)
    
    Returns:
        Notification object vừa tạo
    """
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_url=related_url,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


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
