"""Router Quản lý ứng viên & Lịch phỏng vấn cho Nhà tuyển dụng (/api/employer/applications).
Quy tắc: Kiểm tra quyền backend (401/403/404), < 200 dòng.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.application import Application, ApplicationStatusHistory, MetaApplicationStatus
from app.models.job import Job
from app.models.user import User
from app.schemas.application import AppTabOut, InterviewInfo, StatusHistoryItem
from app.schemas.employer_application import (
    ApplicantCandidateOut, ApplicantJobOut, EmployerApplicationDetailOut,
    EmployerApplicationItemOut, EmployerApplicationListOut,
    EmployerInterviewScheduleIn, EmployerStatusUpdateIn,
)
from app.services.notification import notify_application_status_changed, notify_interview

router = APIRouter(prefix="/employer/applications", tags=["Employer Applications"])

def _smap(db: Session) -> dict[str, MetaApplicationStatus]:
    return {r.slug: r for r in db.scalars(select(MetaApplicationStatus)).all()}

def _iv_info(app_row) -> InterviewInfo | None:
    if not app_row.interview_at:
        return None
    return InterviewInfo(
        interview_at=app_row.interview_at,
        interview_mode=app_row.interview_mode,
        interview_location=app_row.interview_location,
    )

@router.get("", response_model=EmployerApplicationListOut, summary="Danh sách ứng viên nộp hồ sơ")
def list_employer_applications(
    job_id: int | None = Query(None),
    status_filter: str = Query("all", alias="status"),
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user=Depends(role_required("recruiter", "employer")),
    db: Session = Depends(get_db),
):
    sm = _smap(db)
    my_jobs_rows = db.execute(
        select(Job.id, Job.title).where(Job.employer_id == current_user.id).order_by(Job.created_at.desc())
    ).all()
    my_jobs = [ApplicantJobOut(id=r.id, title=r.title) for r in my_jobs_rows]
    my_job_ids = [j.id for j in my_jobs]

    if not my_job_ids:
        return EmployerApplicationListOut(
            items=[], tabs=[AppTabOut(key="all", label="Tất cả", count=0)], jobs=[], total=0, page=page, page_size=page_size
        )

    count_q = select(Application.status, func.count(Application.id)).join(Job, Application.job_id == Job.id).where(Job.employer_id == current_user.id)
    if job_id and job_id in my_job_ids:
        count_q = count_q.where(Application.job_id == job_id)

    raw_counts = dict(db.execute(count_q.group_by(Application.status)).all())
    tabs = [AppTabOut(key="all", label="Tất cả", count=sum(raw_counts.values()))]
    for meta in sorted(sm.values(), key=lambda m: m.sort_order):
        tabs.append(AppTabOut(key=meta.slug, label=meta.name, count=raw_counts.get(meta.slug, 0)))

    base = select(Application, Job.title.label("job_title"), User).join(Job, Application.job_id == Job.id).join(User, Application.candidate_id == User.id).where(Job.employer_id == current_user.id)
    if job_id and job_id in my_job_ids:
        base = base.where(Application.job_id == job_id)
    if status_filter and status_filter != "all":
        base = base.where(Application.status == status_filter)
    if q.strip():
        kw = q.strip()
        base = base.where(User.full_name.ilike(f"%{kw}%") | User.email.ilike(f"%{kw}%") | Job.title.ilike(f"%{kw}%"))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(Application.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    items = [
        EmployerApplicationItemOut(
            id=app_row.id, job=ApplicantJobOut(id=app_row.job_id, title=j_title),
            candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url),
            cv_id=app_row.cv_id, cv_name=app_row.cv_name_snapshot, cover_letter=app_row.cover_letter,
            status=app_row.status, status_label=sm.get(app_row.status).name if sm.get(app_row.status) else app_row.status,
            status_tone=sm.get(app_row.status).tone if sm.get(app_row.status) else "neutral",
            created_at=app_row.created_at, updated_at=app_row.updated_at, interview=_iv_info(app_row),
        ) for app_row, j_title, cand in rows
    ]
    return EmployerApplicationListOut(items=items, tabs=tabs, jobs=my_jobs, total=total, page=page, page_size=page_size)

@router.get("/{app_id}", response_model=EmployerApplicationDetailOut, summary="Chi tiết hồ sơ ứng viên")
def get_employer_application_detail(
    app_id: int, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    row = db.execute(
        select(Application, Job.title.label("job_title"), User).join(Job, Application.job_id == Job.id).join(User, Application.candidate_id == User.id).where(Application.id == app_id, Job.employer_id == current_user.id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại hoặc không thuộc quyền quản lý.")

    app_row, j_title, cand = row
    sm = _smap(db)
    history_rows = db.scalars(
        select(ApplicationStatusHistory).where(ApplicationStatusHistory.application_id == app_id).order_by(ApplicationStatusHistory.changed_at.asc())
    ).all()
    history = [
        StatusHistoryItem(
            status=h.status, status_label=sm.get(h.status).name if sm.get(h.status) else h.status,
            status_tone=sm.get(h.status).tone if sm.get(h.status) else "neutral", note=h.note, changed_at=h.changed_at,
        ) for h in history_rows
    ]

    return EmployerApplicationDetailOut(
        id=app_row.id, job=ApplicantJobOut(id=app_row.job_id, title=j_title),
        candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url),
        cv_id=app_row.cv_id, cv_name=app_row.cv_name_snapshot, cover_letter=app_row.cover_letter,
        status=app_row.status, status_label=sm.get(app_row.status).name if sm.get(app_row.status) else app_row.status,
        status_tone=sm.get(app_row.status).tone if sm.get(app_row.status) else "neutral",
        created_at=app_row.created_at, updated_at=app_row.updated_at, interview=_iv_info(app_row), history=history,
    )

@router.patch("/{app_id}/status", summary="Cập nhật trạng thái hồ sơ")
def update_application_status(
    app_id: int, body: EmployerStatusUpdateIn, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    app = db.scalar(select(Application).join(Job, Application.job_id == Job.id).where(Application.id == app_id, Job.employer_id == current_user.id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    sm = _smap(db)
    if body.status not in sm:
        raise HTTPException(status_code=422, detail="Trạng thái không hợp lệ.")

    app.status = body.status
    app.updated_at = datetime.now(timezone.utc)
    note_text = body.note or f"Nhà tuyển dụng chuyển trạng thái thành: {sm[body.status].name}"
    db.add(ApplicationStatusHistory(application_id=app.id, status=body.status, note=note_text))

    job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
    notify_application_status_changed(
        db, candidate_id=app.candidate_id, status=body.status, status_label=sm[body.status].name,
        job_title=job_title, application_id=app.id, actor_id=current_user.id, note=body.note,
    )
    db.commit()
    return {"message": "Cập nhật trạng thái hồ sơ thành công!", "status": body.status}

@router.post("/{app_id}/interview", summary="Lên lịch hẹn phỏng vấn")
def schedule_interview(
    app_id: int, body: EmployerInterviewScheduleIn, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    app = db.scalar(select(Application).join(Job, Application.job_id == Job.id).where(Application.id == app_id, Job.employer_id == current_user.id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

    app.interview_at = body.interview_at
    app.interview_mode = body.interview_mode
    app.interview_location = body.interview_location
    app.status = "interview"
    app.updated_at = datetime.now(timezone.utc)

    loc_str = f" tại {body.interview_location}" if body.interview_location else ""
    note_text = body.note or f"Lên lịch phỏng vấn {body.interview_mode}{loc_str}"
    db.add(ApplicationStatusHistory(application_id=app.id, status="interview", note=note_text))

    job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
    notify_interview(
        db, candidate_id=app.candidate_id, application_id=app.id, job_title=job_title,
        interview_at=body.interview_at, interview_mode=body.interview_mode,
        interview_location=body.interview_location, actor_id=current_user.id,
    )
    db.commit()
    return {"message": "Đã lên lịch hẹn phỏng vấn thành công!", "interview_at": body.interview_at}
