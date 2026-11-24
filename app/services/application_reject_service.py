"""Service dùng chung xử lý luồng Từ chối hồ sơ ứng viên (đơn lẻ & hàng loạt)."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusHistory,
    Interview,
    MetaRejectionReason,
)
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services.notification import notify_application_status_changed


def _norm(st: str) -> str:
    s = (st or "").strip().upper()
    return ApplicationStatus.REVIEWING.value if s == "SCREENING" else s


def _stored(target_upper: str, prev: str) -> str:
    if target_upper == ApplicationStatus.REVIEWING.value:
        return "screening" if prev.islower() else target_upper
    return target_upper.lower() if prev.islower() else target_upper


def validate_rejection_reason(db: Session, reason_code: str) -> MetaRejectionReason:
    slug = (reason_code or "").strip()
    if not slug:
        raise HTTPException(status_code=422, detail="Vui lòng chọn lý do từ chối hợp lệ.")
    reason = db.scalar(select(MetaRejectionReason).where(MetaRejectionReason.slug == slug))
    if not reason:
        raise HTTPException(status_code=422, detail=f"Mã lý do từ chối '{slug}' không tồn tại.")
    return reason


def reject_application_core(
    db: Session,
    app: Application,
    actor_id: int,
    reason: MetaRejectionReason,
    message: str | None = None,
) -> dict:
    """Thực thi từ chối 1 hồ sơ trong transaction hiện tại (idempotent nếu đã từ chối)."""
    current = _norm(app.status)
    if current == ApplicationStatus.REJECTED.value:
        return {
            "id": app.id,
            "status": app.status,
            "already_rejected": True,
            "reason_code": reason.slug,
            "reason_label": reason.name,
            "cancelled_interviews": 0,
            "message": "Hồ sơ đã ở trạng thái từ chối trước đó.",
        }

    if current not in (
        ApplicationStatus.SUBMITTED.value,
        ApplicationStatus.REVIEWING.value,
        ApplicationStatus.INTERVIEW.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Không thể từ chối hồ sơ đang ở trạng thái cuối '{app.status}'.",
        )

    clean_msg = (message or "").strip() or None
    if clean_msg and len(clean_msg) > 500:
        raise HTTPException(status_code=422, detail="Lời nhắn cho ứng viên tối đa 500 ký tự.")

    now_utc = datetime.now(timezone.utc)
    old_status = app.status
    new_status = _stored(ApplicationStatus.REJECTED.value, old_status)
    app.status = new_status
    app.updated_at = now_utc

    # Hủy các lịch phỏng vấn đang hẹn của hồ sơ này
    scheduled_ivs = list(
        db.scalars(
            select(Interview).where(Interview.application_id == app.id, Interview.status == "scheduled")
        ).all()
    )
    for iv in scheduled_ivs:
        iv.status = "cancelled"
        iv.cancel_reason = f"Hồ sơ bị từ chối: {reason.name}"

    history_note = f"Lý do: {reason.name}" + (f" — {clean_msg}" if clean_msg else "")
    db.add(
        ApplicationStatusHistory(
            application_id=app.id,
            status=new_status,
            old_status=old_status,
            new_status=new_status,
            changed_by_user_id=actor_id,
            note=history_note[:500],
        )
    )

    candidate_id = app.candidate_id
    if candidate_id is None and app.candidate_profile_id is not None:
        candidate_id = db.scalar(
            select(CandidateProfile.user_id).where(CandidateProfile.id == app.candidate_profile_id)
        )
    job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""

    # Thông báo cho ứng viên dùng nhãn lý do thân thiện + lời nhắn (tuyệt đối KHÔNG gửi ghi chú nội bộ)
    friendly_note = f"Lý do: {reason.name}" + (f". Lời nhắn: {clean_msg}" if clean_msg else "")
    if candidate_id is not None:
        notif = notify_application_status_changed(
            db,
            candidate_id=candidate_id,
            status=new_status,
            status_label=f"Không phù hợp ({reason.name})",
            job_title=job_title,
            application_id=app.id,
            actor_id=actor_id,
            note=friendly_note[:500],
        )
        if notif is None:
            raise HTTPException(status_code=500, detail="Không thể tạo thông báo cho ứng viên.")

    return {
        "id": app.id,
        "status": new_status,
        "already_rejected": False,
        "reason_code": reason.slug,
        "reason_label": reason.name,
        "cancelled_interviews": len(scheduled_ivs),
        "message": "Đã từ chối hồ sơ thành công.",
    }
