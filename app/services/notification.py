"""Hàm thông báo dùng chung cho toàn hệ thống.

Mọi module (hồ sơ ứng tuyển, duyệt tin, phỏng vấn...) chỉ cần gọi:

    from app.services.notification import create_notification

    create_notification(
        db,
        user_id=employer.id,
        type=NotificationType.APPLICATION_SUBMITTED,
        title="Có hồ sơ mới",
        message=f"{candidate.full_name} vừa ứng tuyển vị trí {job.title}",
        link=f"/candidate/applications/{app.id}",
        ref_type="application",
        ref_id=app.id,
    )

Nguyên tắc:
    • Không bao giờ ném exception ra ngoài — lỗi tạo thông báo KHÔNG được làm hỏng
      nghiệp vụ chính (nộp hồ sơ, đổi trạng thái...). Lỗi được log và bỏ qua.
    • Có cơ chế dedupe (dedupe_key) để không tạo trùng thông báo khi request lặp lại.
    • Không tự commit: hàm dùng chung cùng transaction với nghiệp vụ gọi nó.
      Nếu nghiệp vụ rollback thì thông báo cũng rollback (đúng nhất quán).
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.notification import Notification



# ---------------------------------------------------------------------------
# Các loại thông báo (dùng để FE lọc / hiển thị icon, màu)
# ---------------------------------------------------------------------------
class NotificationType:
    """Hằng số cho cột `notifications.type`.

    Dùng hằng số (thay vì Enum trong MySQL) để không phải ALTER bảng khi thêm loại mới.
    """

    # Ứng viên -> nhà tuyển dụng
    APPLICATION_SUBMITTED = "application_submitted"
    # Nhà tuyển dụng -> ứng viên
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    APPLICATION_INTERVIEW = "application_interview"
    # Tin tuyển dụng
    JOB_SUBMITTED = "job_submitted"
    JOB_APPROVED = "job_approved"
    JOB_REJECTED = "job_rejected"
    # Hồ sơ / CV
    CV_UPLOADED = "cv_uploaded"
    CV_DELETED = "cv_deleted"
    # Hệ thống
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Nội dung mẫu theo loại thông báo
# ---------------------------------------------------------------------------
_TYPE_TITLES: dict[str, str] = {
    NotificationType.APPLICATION_SUBMITTED: "Có hồ sơ ứng tuyển mới",
    NotificationType.APPLICATION_STATUS_CHANGED: "Hồ sơ của bạn đã được cập nhật",
    NotificationType.APPLICATION_INTERVIEW: "Lời mời phỏng vấn",
    NotificationType.JOB_SUBMITTED: "Đã gửi tin chờ duyệt",
    NotificationType.JOB_APPROVED: "Tin tuyển dụng đã được duyệt",
    NotificationType.JOB_REJECTED: "Tin tuyển dụng chưa được duyệt",
    NotificationType.CV_UPLOADED: "CV đã được tải lên thành công",
    NotificationType.CV_DELETED: "CV đã được xoá",
    NotificationType.SYSTEM: "Thông báo từ hệ thống",
}


def _log_error(message: str) -> None:
    """In log lỗi mà không phụ thuộc encoding console (cp1252 trên Windows)."""
    try:
        print(f"[NOTIFICATION] {message}")
    except UnicodeEncodeError:
        print(
            f"[NOTIFICATION] {message}".encode("utf-8", "replace").decode("ascii", "replace")
        )



# ---------------------------------------------------------------------------
# Hàm chính
# ---------------------------------------------------------------------------
def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str | None = None,
    message: str | None = None,
    actor_id: int | None = None,
    link: str | None = None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    dedupe_key: str | None = None,
    commit: bool = False,
) -> Notification | None:
    """Tạo 1 thông báo cho người dùng `user_id`.

    Tham số:
        db        : SQLAlchemy Session (dùng chung transaction với nghiệp vụ gọi)
        user_id   : id người NHẬN thông báo
        type      : loại thông báo, xem class NotificationType
        title     : tiêu đề; nếu bỏ trống sẽ lấy mặc định theo `type`
        message   : nội dung chi tiết
        actor_id  : id người gây ra sự kiện (người gửi), có thể None
        link      : đường dẫn FE mở khi bấm vào thông báo
        ref_type  : loại đối tượng liên quan ("application", "job", "cv"...)
        ref_id    : id đối tượng liên quan
        dedupe_key: khoá chống trùng (duy nhất theo user). Nếu đã tồn tại -> trả None
        commit    : True = tự commit (dùng khi gọi ngoài transaction nào);
                    False (mặc định) = để transaction của caller quyết định

    Trả về:
        Notification nếu tạo thành công, None nếu bị bỏ qua (trùng dedupe_key
        hoặc có lỗi DB — lỗi KHÔNG làm hỏng nghiệp vụ gọi).
    """
    if not user_id:
        return None

    if dedupe_key:
        existing = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.dedupe_key == dedupe_key,
            )
        )
        if existing is not None:
            return None

    notification = Notification(
        user_id=user_id,
        actor_id=actor_id,
        type=type,
        title=(title or _TYPE_TITLES.get(type) or "Thông báo")[:255],
        message=message,
        link=link,
        ref_type=ref_type,
        ref_id=ref_id,
        is_read=False,
        dedupe_key=dedupe_key,
    )

    # Dùng SAVEPOINT (nested transaction) thay vì rollback() thật.
    # Nếu insert lỗi -> chỉ rollback phần thông báo, KHÔNG mất thay đổi
    # nghiệp vụ đang chờ commit trong cùng transaction (vd: hồ sơ ứng tuyển).
    try:
        with db.begin_nested():
            db.add(notification)
            db.flush()  # lấy notification.id mà chưa commit
        if commit:
            db.commit()
            db.refresh(notification)
    except IntegrityError as error:
        # Có thể là: (a) trùng dedupe_key do race condition, (b) vi phạm FK
        # (user_id/actor_id không tồn tại). Cả 2 đều -> bỏ qua, không làm hỏng nghiệp vụ.
        detail = str(getattr(error, "orig", error))
        if "Duplicate" in detail or "duplicate" in detail:
            _log_error(f"Bỏ qua thông báo trùng: user_id={user_id}, dedupe_key={dedupe_key}")
        else:
            _log_error(f"Không tạo được thông báo (lỗi ràng buộc) cho user_id={user_id}: {detail}")
        return None
    except SQLAlchemyError as error:
        _log_error(f"Không tạo được thông báo cho user_id={user_id}: {error}")
        if commit:
            try:
                db.rollback()
            except SQLAlchemyError:
                pass
        return None

    return notification



# ---------------------------------------------------------------------------
# Hàm tiện ích cho từng sự kiện nghiệp vụ
# ---------------------------------------------------------------------------
def notify_application_submitted(
    db: Session,
    *,
    employer_id: int,
    candidate_name: str,
    job_title: str,
    application_id: int,
    candidate_id: int | None = None,
    commit: bool = False,
) -> Notification | None:
    """Thông báo cho nhà tuyển dụng: có hồ sơ ứng tuyển mới."""
    return create_notification(
        db,
        user_id=employer_id,
        actor_id=candidate_id,
        type=NotificationType.APPLICATION_SUBMITTED,
        title="Có hồ sơ ứng tuyển mới",
        message=f"{candidate_name} vừa ứng tuyển vị trí {job_title}.",
        link=f"/pages/employer/applications.html?app_id={application_id}",
        ref_type="application",
        ref_id=application_id,
        dedupe_key=f"application:{application_id}:submitted",
        commit=commit,
    )


def notify_application_status_changed(
    db: Session,
    *,
    candidate_id: int,
    status: str,
    status_label: str,
    job_title: str,
    application_id: int,
    actor_id: int | None = None,
    note: str | None = None,
    commit: bool = False,
) -> Notification | None:
    """Thông báo cho ứng viên: hồ sơ chuyển sang trạng thái mới."""
    message = f"Hồ sơ ứng tuyển vị trí {job_title} đã chuyển sang trạng thái '{status_label}'."
    if note:
        message = f"{message} {note}"
    return create_notification(
        db,
        user_id=candidate_id,
        actor_id=actor_id,
        type=NotificationType.APPLICATION_STATUS_CHANGED,
        title="Hồ sơ của bạn đã được cập nhật",
        message=message,
        link=f"/pages/candidate/applications.html?app_id={application_id}",
        ref_type="application",
        ref_id=application_id,
        dedupe_key=f"application:{application_id}:status:{status}",
        commit=commit,
    )


def notify_job_status_changed(
    db: Session,
    *,
    employer_id: int,
    job_id: int,
    job_title: str,
    status: str,
    status_label: str,
    actor_id: int | None = None,
    note: str | None = None,
    commit: bool = False,
) -> Notification | None:
    """Thông báo cho nhà tuyển dụng: tin tuyển dụng đổi trạng thái (duyệt / từ chối / đăng...)."""
    if status == "published":
        notif_type = NotificationType.JOB_APPROVED
    elif status == "rejected":
        notif_type = NotificationType.JOB_REJECTED
    else:
        notif_type = NotificationType.JOB_SUBMITTED

    message = f"Tin tuyển dụng '{job_title}' hiện ở trạng thái '{status_label}'."
    if note:
        message = f"{message} {note}"

    return create_notification(
        db,
        user_id=employer_id,
        actor_id=actor_id,
        type=notif_type,
        title=_TYPE_TITLES.get(notif_type, "Thông báo"),
        message=message,
        link=f"/pages/employer/jobs.html?job_id={job_id}",
        ref_type="job",
        ref_id=job_id,
        dedupe_key=f"job:{job_id}:status:{status}",
        commit=commit,
    )



# ---------------------------------------------------------------------------
# Truy vấn phục vụ API
# ---------------------------------------------------------------------------
def count_unread(db: Session, user_id: int) -> int:
    """Đếm số thông báo chưa đọc của user."""
    return (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        or 0
    )


def mark_as_read(db: Session, user_id: int, notification_ids: list[int]) -> int:
    """Đánh dấu đã đọc cho danh sách thông báo thuộc user. Trả về số bản ghi đã đổi."""
    if not notification_ids:
        return 0
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.id.in_(notification_ids),
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=now)
    )
    return int(result.rowcount or 0)


def mark_all_as_read(db: Session, user_id: int) -> int:
    """Đánh dấu đã đọc toàn bộ thông báo của user. Trả về số bản ghi đã đổi."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=now)
    )
    return int(result.rowcount or 0)


def delete_all_notifications(db: Session, user_id: int) -> int:
    """Xoá toàn bộ thông báo của user. Trả về số bản ghi đã xoá."""
    result = db.execute(
        Notification.__table__.delete().where(Notification.user_id == user_id)
    )
    return int(result.rowcount or 0)


def serialize_notification(
    notification: Notification, actor_name: str | None = None
) -> dict[str, Any]:
    """Chuyển model sang dict cho response (giữ đúng key mà FE cần)."""
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "ref_type": notification.ref_type,
        "ref_id": notification.ref_id,
        "is_read": bool(notification.is_read),
        "read_at": notification.read_at,
        "actor_id": notification.actor_id,
        "actor_name": actor_name,
        "created_at": notification.created_at,
    }


def notify_interview(
    db: Session,
    *,
    candidate_id: int,
    application_id: int,
    job_title: str,
    interview_at: datetime,
    interview_mode: str | None = None,
    interview_location: str | None = None,
    actor_id: int | None = None,
    commit: bool = False,
) -> Notification | None:
    """Thông báo cho ứng viên: được mời phỏng vấn."""
    when = interview_at.strftime("%H:%M %d/%m/%Y") if interview_at else "sắp tới"
    detail = " · ".join(x for x in (interview_mode, interview_location) if x)
    message = f"Bạn được mời phỏng vấn vị trí {job_title} vào {when}."
    if detail:
        message = f"{message} {detail}"
    return create_notification(
        db,
        user_id=candidate_id,
        actor_id=actor_id,
        type=NotificationType.APPLICATION_INTERVIEW,
        title="Lời mời phỏng vấn",
        message=message,
        link=f"/pages/candidate/applications.html?app_id={application_id}",
        ref_type="application",
        ref_id=application_id,
        dedupe_key=f"application:{application_id}:interview",
        commit=commit,
    )
