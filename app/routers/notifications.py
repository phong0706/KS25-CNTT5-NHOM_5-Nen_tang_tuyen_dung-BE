"""Router thông báo: danh sách, so chua doc, danh dau da doc.

Moi endpoint deu dung chung prefix "/notifications" va deu yeu cau dang nhap.
"""
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    MarkReadRequest,
    MarkReadResultOut,
    NotificationListOut,
    NotificationOut,
    UnreadCountOut,
)
from app.services.notification import (
    build_notification_content,
    count_unread,
    delete_all_notifications,
    mark_all_as_read,
    mark_as_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

PAGE_SIZE = 10


# -- LIST ---------------------------------------------------------------
@router.get("", response_model=NotificationListOut, summary="Danh sách thông báo của tôi")
def list_notifications(
    cursor: str | None = Query(None, description="Con trỏ phân trang (created_at|id)"),
    unread_only: bool = Query(False, description="Chỉ lấy thông báo chưa đọc"),
    type_filter: str | None = Query(None, alias="type", description="Lọc theo loại thông báo"),
    limit: int = Query(PAGE_SIZE, ge=1, le=50, description="Số lượng mục mỗi trang"),
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actual_limit = page_size or limit
    base = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        base = base.where((Notification.read_at.is_(None)) | (Notification.is_read == False))  # noqa: E712
    if type_filter:
        base = base.where(Notification.type == type_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    next_cursor = None

    if cursor:
        try:
            if "|" in cursor:
                dt_str, id_str = cursor.split("|", 1)
                cursor_dt, cursor_id = datetime.fromisoformat(dt_str), int(id_str)
                base = base.where(
                    (Notification.created_at < cursor_dt)
                    | ((Notification.created_at == cursor_dt) & (Notification.id < cursor_id))
                )
            else:
                base = base.where(Notification.id < int(cursor))
        except Exception:
            pass
        query = base.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(actual_limit + 1)
    else:
        current_page = page or 1
        query = base.order_by(Notification.created_at.desc(), Notification.id.desc()).offset((current_page - 1) * actual_limit).limit(actual_limit + 1)

    rows = list(db.scalars(query).all())
    if len(rows) > actual_limit:
        rows = rows[:actual_limit]
        next_cursor = f"{rows[-1].created_at.isoformat()}|{rows[-1].id}"

    items = []
    for n in rows:
        title, body, href = build_notification_content(n.type, n.payload_json, n.title, n.message, n.link)
        is_read = bool(n.read_at is not None or n.is_read)
        items.append(
            NotificationOut(
                id=n.id, type=n.type, title=title, body=body, href=href,
                created_at=n.created_at, read=is_read, is_read=is_read, read_at=n.read_at,
                message=body, link=href, ref_type=n.entity_type or n.ref_type,
                ref_id=n.entity_id or n.ref_id, actor_id=n.actor_id,
            )
        )

    return NotificationListOut(
        items=items, next_cursor=next_cursor, total=total,
        page=page or 1, page_size=actual_limit,
        total_pages=math.ceil(total / actual_limit) if total else 0,
        unread_count=count_unread(db, current_user.id),
    )


# -- UNREAD COUNT -------------------------------------------------------
@router.get("/unread-count", response_model=UnreadCountOut, summary="Số thông báo chưa đọc")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FE gọi endpoint này để hiển thị badge chuông thông báo."""
    return UnreadCountOut(unread_count=count_unread(db, current_user.id))


# -- MARK AS READ -------------------------------------------------------
@router.post("/read", response_model=MarkReadResultOut, summary="Đánh dấu đã đọc (một hoặc nhiều)")
def mark_notifications_read(
    body: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đánh dấu đã đọc cho danh sách id thông báo thuộc user hiện tại."""
    updated = mark_as_read(db, current_user.id, body.notification_ids)
    db.commit()
    return MarkReadResultOut(
        updated=updated,
        unread_count=count_unread(db, current_user.id),
        message=f"Đã đánh dấu {updated} thông báo là đã đọc.",
    )


@router.post("/read-all", response_model=MarkReadResultOut, summary="Đánh dấu đã đọc toàn bộ")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đánh dấu đã đọc TẤT CẢ thông báo của người đang đăng nhập."""
    updated = mark_all_as_read(db, current_user.id)
    db.commit()
    return MarkReadResultOut(
        updated=updated,
        unread_count=0,
        message=f"Đã đánh dấu {updated} thông báo là đã đọc.",
    )


@router.post("/{notification_id}/read", response_model=MarkReadResultOut, summary="Đánh dấu 1 thông báo đã đọc")
def mark_one_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dùng khi người dùng bấm vào 1 thông báo trên danh sách.
    Chỉ áp dụng cho thông báo của chính user, người khác trả 404.
    """
    notif = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thông báo không tồn tại.",
        )

    now = datetime.now(timezone.utc)
    notif.is_read = True
    notif.read_at = now
    db.commit()
    return MarkReadResultOut(
        updated=1,
        unread_count=count_unread(db, current_user.id),
        message="Đã đánh dấu thông báo là đã đọc.",
    )


# -- DELETE -------------------------------------------------------------
@router.delete("", status_code=status.HTTP_200_OK, summary="Xoa toan bo thong bao cua toi")
def delete_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xoa toan bo thong bao cua nguoi dang dang nhap."""
    deleted = delete_all_notifications(db, current_user.id)
    db.commit()
    return {"deleted": deleted, "message": f"Da xoa {deleted} thong bao."}

