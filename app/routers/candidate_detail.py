"""Router: chi tiết hồ sơ ứng tuyển, rút hồ sơ, kiểm tra đã ứng tuyển."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.application import Application, ApplicationStatusHistory, MetaApplicationStatus
from app.models.job import Job
from app.models.company import Company
from app.schemas.application import (
    AppAllowedAction,
    ApplicationDetailOut,
    AppJobSummary,
    InterviewInfo,
    StatusHistoryItem,
    WithdrawRequest,
)
from app.services.notification import (
    NotificationType,
    create_notification,
    notify_application_status_changed,
)

router = APIRouter(tags=["Candidate Applications"])


def _smap(db: Session) -> dict:
    return {r.slug: r for r in db.scalars(select(MetaApplicationStatus)).all()}


def _actions(st, sm):
    acts = [AppAllowedAction(key="view_job", label="Xem tin"),
            AppAllowedAction(key="view_cv", label="Xem CV")]
    meta = sm.get(st)
    if meta and not meta.is_terminal:
        acts.append(AppAllowedAction(key="withdraw", label="Rút hồ sơ"))
    return acts


# ── DETAIL ────────────────────────────────────────────────────

@router.get("/candidate/applications/{app_id}", response_model=ApplicationDetailOut)
def get_application(
    app_id: int,
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    sm = _smap(db)

    row = db.execute(
        select(
            Application,
            Job.id.label("jid"), Job.title, Company.slug.label("company_slug"), Company.name.label("company_name"),
            Job.location, Job.salary_min, Job.salary_max,
            Job.is_salary_negotiable, Job.work_type, Job.status.label("job_status"),
        )
        .join(Job, Application.job_id == Job.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Application.id == app_id, Application.candidate_id == current_user.id)
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Hồ sơ không tồn tại.")

    app = row[0]
    meta = sm.get(app.status)

    job_summary = AppJobSummary(
        id=row.jid, title=row.title, company_slug=row.company_slug, company_name=row.company_name,
        location=row.location, salary_min=row.salary_min, salary_max=row.salary_max,
        is_salary_negotiable=row.is_salary_negotiable, work_type=row.work_type,
        status=row.job_status,
    )

    # Timeline
    history_rows = db.scalars(
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == app_id)
        .order_by(ApplicationStatusHistory.changed_at.asc())
    ).all()

    history = []
    for h in history_rows:
        hmeta = sm.get(h.status)
        history.append(StatusHistoryItem(
            status=h.status,
            status_label=hmeta.name if hmeta else h.status,
            status_tone=hmeta.tone if hmeta else "neutral",
            note=h.note,
            changed_at=h.changed_at,
        ))

    interview = None
    if app.interview_at:
        interview = InterviewInfo(
            interview_at=app.interview_at,
            interview_mode=app.interview_mode,
            interview_location=app.interview_location,
        )

    return ApplicationDetailOut(
        id=app.id, job=job_summary, cv_name=app.cv_name_snapshot,
        cv_id=app.cv_id, cover_letter=app.cover_letter,
        status=app.status,
        status_label=meta.name if meta else app.status,
        status_tone=meta.tone if meta else "neutral",
        created_at=app.created_at, updated_at=app.updated_at,
        history=history, interview=interview,
        allowed_actions=_actions(app.status, sm),
    )


# ── WITHDRAW ──────────────────────────────────────────────────

@router.post("/candidate/applications/{app_id}/withdraw", status_code=200)
def withdraw_application(
    app_id: int,
    body: WithdrawRequest,
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    sm = _smap(db)
    app = db.scalar(
        select(Application).where(
            Application.id == app_id, Application.candidate_id == current_user.id
        )
    )
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ không tồn tại.")

    meta = sm.get(app.status)
    if meta and meta.is_terminal:
        raise HTTPException(status_code=409, detail="Không thể rút hồ sơ ở trạng thái hiện tại.")

    now = datetime.now(timezone.utc)
    app.status = "withdrawn"
    app.active_flag = None
    app.withdraw_reason = body.reason
    app.withdrawn_at = now
    app.updated_at = now

    db.add(ApplicationStatusHistory(
        application_id=app.id, status="withdrawn",
        note=body.reason or "Ứng viên chủ động rút hồ sơ",
        changed_at=now,
    ))

    # ── Thông báo cho nhà tuyển dụng: ứng viên đã rút hồ sơ ──
    job = db.get(Job, app.job_id)
    if job is not None:
        create_notification(
            db,
            user_id=job.employer_id,
            actor_id=current_user.id,
            type=NotificationType.APPLICATION_STATUS_CHANGED,
            title="Ứng viên đã rút hồ sơ",
            message=(
                f"{current_user.full_name} đã rút hồ sơ ứng tuyển vị trí {job.title}."
                + (f" Lý do: {body.reason}" if body.reason else "")
            ),
            link=f"/pages/employer/applications.html?app_id={app.id}",
            ref_type="application",
            ref_id=app.id,
            dedupe_key=f"application:{app.id}:status:withdrawn",
        )

    db.commit()

    return {"message": "Rút hồ sơ thành công.", "status": "withdrawn"}


# ── CHECK APPLIED ─────────────────────────────────────────────

@router.get("/jobs/{job_id}/applied", summary="Kiểm tra đã ứng tuyển chưa")
def check_applied(
    job_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.scalar(
        select(Application).where(
            Application.candidate_id == current_user.id,
            Application.job_id == job_id,
            Application.active_flag == 1,
        )
    )
    if app:
        return {"applied": True, "application_id": app.id, "status": app.status}
    return {"applied": False}

