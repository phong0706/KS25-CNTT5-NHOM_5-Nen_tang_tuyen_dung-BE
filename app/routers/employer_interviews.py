"""Router Quản lý Lịch phỏng vấn cho Nhà tuyển dụng (/api/employer/interviews).
Tuân thủ: < 200 dòng, kiểm tra quyền backend (401/403/404), trả về giờ UTC / client hiển thị Asia/Ho_Chi_Minh.
"""
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.employer_scope import EmployerScope, get_employer_scope
from app.db.session import get_db
from app.models.application import Application, Interview
from app.models.job import Job
from app.models.user import User
from app.schemas.employer_application import (
    EmployerInterviewScheduleIn, InterviewCancelIn, InterviewItemOut
)
from app.services.interview_service import check_interview_overlap
from app.services.notification import (
    notify_interview_changed,
    notify_interview_cancelled,
)

router = APIRouter(prefix="/employer/interviews", tags=["Employer Interviews"])


@router.get("", response_model=list[InterviewItemOut], summary="Danh sách lịch phỏng vấn theo tuần/khoảng thời gian")
def list_interviews(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    job_id: int | None = Query(None),
    status: str | None = Query(None),
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Interview, Application, Job, User)
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(User, Application.candidate_id == User.id)
        .where(Job.company_id == scope.company_id, Job.deleted_at.is_(None))
    )
    if job_id:
        stmt = stmt.where(Job.id == job_id)
    if status and status != "all":
        stmt = stmt.where(Interview.status == status)
    if from_date:
        stmt = stmt.where(Interview.scheduled_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        stmt = stmt.where(Interview.scheduled_at <= datetime.combine(to_date, datetime.max.time()))

    rows = db.execute(stmt.order_by(Interview.scheduled_at.asc())).all()
    return [
        InterviewItemOut(
            id=iv.id,
            application_id=iv.application_id,
            candidate_name=cand.full_name or "Ứng viên",
            candidate_avatar=cand.avatar_url,
            candidate_email=cand.email,
            job_id=job.id,
            job_title=job.title,
            scheduled_at=iv.scheduled_at,
            duration_min=iv.duration_min or 45,
            mode=iv.mode,
            location_or_link=iv.location_or_link,
            interviewer=iv.interviewer,
            note=iv.note,
            status=iv.status,
            cancel_reason=iv.cancel_reason,
        )
        for iv, app, job, cand in rows
    ]


@router.patch("/{interview_id}/reschedule", summary="Đổi lịch phỏng vấn")
def reschedule_interview(
    interview_id: int,
    body: EmployerInterviewScheduleIn,
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    iv = db.scalar(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .where(Interview.id == interview_id, Job.company_id == scope.company_id, Job.deleted_at.is_(None))
    )
    if not iv:
        raise HTTPException(status_code=404, detail="Lịch phỏng vấn không tồn tại hoặc không thuộc quyền quản lý.")

    now_dt = datetime.now() if body.scheduled_at.tzinfo is None else datetime.now(timezone.utc)
    if body.scheduled_at < now_dt - timedelta(minutes=5):
        raise HTTPException(
            status_code=400,
            detail="Thời gian phỏng vấn không thể ở trong quá khứ. Vui lòng chọn ngày và giờ trong tương lai.",
        )

    if not body.force:
        overlap = check_interview_overlap(db, scope.user_id, body.scheduled_at, body.duration_min, exclude_id=iv.id)
        if overlap:
            raise HTTPException(
                status_code=409,
                detail={"message": "Trùng lịch phỏng vấn", "conflict": overlap},
            )

    iv.scheduled_at = body.scheduled_at
    iv.duration_min = body.duration_min
    if body.mode:
        iv.mode = body.mode
    if body.location_or_link is not None:
        iv.location_or_link = body.location_or_link
    if body.interviewer is not None:
        iv.interviewer = body.interviewer
    if body.note is not None:
        iv.note = body.note
    iv.status = "scheduled"

    # Cập nhật snapshot trên application & gửi notification
    app = db.scalar(select(Application).where(Application.id == iv.application_id))
    if app:
        app.interview_at = body.scheduled_at
        app.interview_mode = body.mode
        app.interview_location = body.location_or_link
        job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
        notify_interview_changed(
            db,
            candidate_id=app.candidate_id,
            application_id=app.id,
            job_title=job_title,
            interview_at=body.scheduled_at,
            actor_id=scope.user_id,
        )

    db.commit()
    return {"message": "Đã đổi lịch phỏng vấn thành công!", "scheduled_at": iv.scheduled_at}


@router.post("/{interview_id}/cancel", summary="Hủy lịch phỏng vấn")
def cancel_interview(
    interview_id: int,
    body: InterviewCancelIn,
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    iv = db.scalar(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .where(Interview.id == interview_id, Job.company_id == scope.company_id, Job.deleted_at.is_(None))
    )
    if not iv:
        raise HTTPException(status_code=404, detail="Lịch phỏng vấn không tồn tại.")

    iv.status = "cancelled"
    iv.cancel_reason = body.reason

    app = db.scalar(select(Application).where(Application.id == iv.application_id))
    if app:
        job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
        notify_interview_cancelled(
            db,
            candidate_id=app.candidate_id,
            application_id=app.id,
            job_title=job_title,
            reason=body.reason,
            actor_id=scope.user_id,
        )

    db.commit()
    return {"message": "Đã hủy lịch phỏng vấn thành công!"}


@router.post("/{interview_id}/done", summary="Đánh dấu đã hoàn thành phỏng vấn")
def mark_interview_done(
    interview_id: int,
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    iv = db.scalar(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .where(Interview.id == interview_id, Job.company_id == scope.company_id, Job.deleted_at.is_(None))
    )
    if not iv:
        raise HTTPException(status_code=404, detail="Lịch phỏng vấn không tồn tại.")

    iv.status = "done"
    db.commit()
    return {"message": "Đã cập nhật trạng thái phỏng vấn: Đã hoàn thành!"}
