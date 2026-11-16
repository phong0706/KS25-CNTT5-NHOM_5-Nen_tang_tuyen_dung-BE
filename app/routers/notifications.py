"""Router thông báo: danh sách, so chua doc, danh dau da doc.

Moi endpoint deu dung chung prefix "/notifications" va deu yeu cau dang nhap.
"""
import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
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
    count_unread,
    delete_all_notifications,
    mark_all_as_read,
    mark_as_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

PAGE_SIZE = 10


def _actor_names(db: Session, notifications: list[Notification]) -> dict[int, str]:
    """Lay ten nguoi gui theo actor_id (tranh N+1 query)."""
    actor_ids = {n.actor_id for n in notifications if n.actor_id}
    if not actor_ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(actor_ids))).all()
    return {row[0]: row[1] for row in rows}



# -- LIST ---------------------------------------------------------------
@router.get("", response_model=NotificationListOut, summary="Danh sach thong bao cua toi")
def list_notifications(
    unread_only: bool = Query(False, description="Chi lay thong bao chua doc"),
    type_filter: str | None = Query(None, alias="type", description="Loc theo loai thong bao"),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tra ve danh sach thong bao cua nguoi dang dang nhap, moi nhat truoc.

    Luong:
        1. Loc theo user_id (luon luon), them unread_only / type neu co.
        2. Dem tong + dem so chua doc (tra kem de FE hien thi badge).
        3. Phan trang, sap xep created_at DESC.
    """
    base = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        base = base.where(Notification.is_read == False)  # noqa: E712
    if type_filter:
        base = base.where(Notification.type == type_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    rows = db.scalars(
        base.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    names = _actor_names(db, list(rows))
    items = [
        NotificationOut(
            id=n.id,
            type=n.type,
            title=n.title,
            message=n.message,
            link=n.link,
            ref_type=n.ref_type,
            ref_id=n.ref_id,
            is_read=bool(n.is_read),
            read_at=n.read_at,
            actor_id=n.actor_id,
            actor_name=names.get(n.actor_id) if n.actor_id else None,
            created_at=n.created_at,
        )
        for n in rows
    ]

    return NotificationListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
        unread_count=count_unread(db, current_user.id),
    )


# -- UNREAD COUNT -------------------------------------------------------
@router.get("/unread-count", response_model=UnreadCountOut, summary="So thong bao chua doc")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FE goi endpoint nay de hien thi badge chuong thong bao."""
    return UnreadCountOut(unread_count=count_unread(db, current_user.id))


# -- MARK AS READ -------------------------------------------------------
@router.post("/read", response_model=MarkReadResultOut, summary="Danh dau da doc (mot hoac nhieu)")
def mark_notifications_read(
    body: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh dau da doc cho danh sach id thong bao.

    Chi danh dau duoc thong bao CUA CHINH nguoi dang dang nhap (dieu kien user_id).
    """
    updated = mark_as_read(db, current_user.id, body.notification_ids)
    db.commit()
    return MarkReadResultOut(
        updated=updated,
        unread_count=count_unread(db, current_user.id),
        message=f"Da danh dau {updated} thong bao la da doc.",
    )


@router.post("/read-all", response_model=MarkReadResultOut, summary="Danh dau da doc toan bo")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh dau da doc TAT CA thong bao cua nguoi dang dang nhap."""
    updated = mark_all_as_read(db, current_user.id)
    db.commit()
    return MarkReadResultOut(
        updated=updated,
        unread_count=0,
        message=f"Da danh dau {updated} thong bao la da doc.",
    )


@router.post("/{notification_id}/read", response_model=MarkReadResultOut, summary="Danh dau 1 thong bao da doc")
def mark_one_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dung khi nguoi dung bam vao 1 thong bao tren danh sach."""
    updated = mark_as_read(db, current_user.id, [notification_id])
    db.commit()
    return MarkReadResultOut(
        updated=updated,
        unread_count=count_unread(db, current_user.id),
        message="Da danh dau thong bao la da doc.",
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

