"""Router: nộp hồ sơ, danh sách ứng tuyển, chi tiết, rút hồ sơ."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.application import (
    Application,
    ApplicationStatusHistory,
    MetaApplicationStatus,
    CV,
)
from app.models.job import Job
from app.models.company import Company
from app.schemas.application import (
    AppAllowedAction,
    ApplicationCardOut,
    ApplicationDetailOut,
    ApplicationListOut,
    AppJobSummary,
    AppTabOut,
    ApplyOut,
    ApplyRequest,
    InterviewInfo,
    StatusHistoryItem,
    WithdrawRequest,
)
from app.services.notification import notify_application_submitted

router = APIRouter(tags=["Candidate Applications"])

# ── Helpers ───────────────────────────────────────────────────

_JOB_COLS = (
    Job.id,
    Job.title,
    Company.slug.label("company_slug"),
    Company.name.label("company_name"),
    Company.logo_url.label("company_logo"),
    Company.logo_url_2x.label("company_logo_2x"),
    Company.logo_version.label("company_logo_version"),
    Job.location,
    Job.salary_min,
    Job.salary_max,
    Job.is_salary_negotiable,
    Job.work_type,
    Job.status.label("job_status"),
)


def _smap(db: Session) -> dict[str, MetaApplicationStatus]:
    return {r.slug: r for r in db.scalars(select(MetaApplicationStatus)).all()}


def _job_summary(r) -> AppJobSummary:
    logo = getattr(r, "company_logo", None)
    logo_2x = getattr(r, "company_logo_2x", None)
    ver = getattr(r, "company_logo_version", None)
    if logo and ver:
        logo = f"{logo}?v={ver}"
    if logo_2x and ver:
        logo_2x = f"{logo_2x}?v={ver}"
    return AppJobSummary(
        id=r.id, title=r.title, company_slug=getattr(r, "company_slug", None), company_name=r.company_name,
        company_logo=logo, company_logo_2x=logo_2x,
        location=r.location, salary_min=r.salary_min, salary_max=r.salary_max,
        is_salary_negotiable=r.is_salary_negotiable, work_type=r.work_type,
        status=r.job_status,
    )


def _actions(st: str, sm: dict) -> list[AppAllowedAction]:
    acts = [AppAllowedAction(key="view_job", label="Xem tin"),
            AppAllowedAction(key="view_cv", label="Xem CV")]
    meta = sm.get(st)
    if meta and not meta.is_terminal:
        acts.append(AppAllowedAction(key="withdraw", label="Rút hồ sơ"))
    return acts


# ── APPLY ─────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/apply", response_model=ApplyOut, summary="Nộp hồ sơ ứng tuyển")
def apply_job(
    job_id: int,
    body: ApplyRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    # Kiểm tra idempotency
    if idempotency_key:
        existing = db.scalar(
            select(Application).where(
                Application.candidate_id == current_user.id,
                Application.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return ApplyOut(application_id=existing.id, status=existing.status,
                           message="Hồ sơ đã được nộp trước đó.")

    # Kiểm tra đã nộp chưa (active_flag = 1)
    dup = db.scalar(
        select(Application).where(
            Application.candidate_id == current_user.id,
            Application.job_id == job_id,
            Application.active_flag == 1,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail="Bạn đã ứng tuyển vị trí này rồi.")

    # Kiểm tra tin đang tuyển
    job = db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Tin tuyển dụng không tồn tại.")
    if job.status != "published":
        raise HTTPException(status_code=422, detail="Tin tuyển dụng đã đóng hoặc hết hạn.")
    if job.deadline and job.deadline < datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="Tin tuyển dụng đã hết hạn nộp hồ sơ.")

    # Kiểm tra CV thuộc về ứng viên và chưa bị xóa mềm
    cv = db.scalar(select(CV).where(CV.id == body.cv_id, CV.candidate_id == current_user.id, CV.deleted_at.is_(None)))
    if not cv:
        raise HTTPException(status_code=422, detail="CV không hợp lệ.")

    app = Application(
        candidate_id=current_user.id,
        job_id=job_id,
        cv_id=cv.id,
        cv_name_snapshot=cv.original_name,
        cover_letter=body.cover_letter,
        status="submitted",
        active_flag=1,
        idempotency_key=idempotency_key,
    )
    db.add(app)
    db.flush()

    db.add(ApplicationStatusHistory(
        application_id=app.id, status="submitted", note="Ứng viên nộp hồ sơ"
    ))

    # ── Thông báo cho nhà tuyển dụng: có hồ sơ mới ──
    # Gọi TRƯỚC db.commit() để thông báo nằm cùng transaction với hồ sơ.
    # Nếu commit lỗi -> hồ sơ và thông báo cùng rollback (không có thông báo ma).
    # Hàm tự bắt lỗi nên không làm hỏng luồng nộp hồ sơ.
    notify_application_submitted(
        db,
        employer_id=job.employer_id,
        candidate_id=current_user.id,
        candidate_name=current_user.full_name,
        job_title=job.title,
        application_id=app.id,
        job_id=job.id,
    )

    db.commit()
    db.refresh(app)

    return ApplyOut(application_id=app.id, status="submitted",
                    message="Nộp hồ sơ thành công!")


# ── LIST ──────────────────────────────────────────────────────

@router.get("/candidate/applications", response_model=ApplicationListOut)
def list_applications(
    status_filter: str = Query("all", alias="status"),
    q: str = Query("", max_length=100),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    sm = _smap(db)
    page_size = 10

    # Tab counts
    count_q = (
        select(Application.status, func.count(Application.id))
        .where(Application.candidate_id == current_user.id)
        .group_by(Application.status)
    )
    raw_counts: dict[str, int] = {}
    for row in db.execute(count_q).all():
        raw_counts[row[0]] = row[1]
    total_all = sum(raw_counts.values())

    tabs = [AppTabOut(key="all", label="Tất cả", count=total_all)]
    for meta in sorted(sm.values(), key=lambda m: m.sort_order):
        tabs.append(AppTabOut(key=meta.slug, label=meta.name, count=raw_counts.get(meta.slug, 0)))

    # Base query
    base = (
        select(
            Application.id,
            Application.cv_id,
            Application.cv_name_snapshot,
            Application.cover_letter,
            Application.status,
            Application.interview_at,
            Application.interview_mode,
            Application.interview_location,
            Application.created_at,
            Application.updated_at,
            *_JOB_COLS,
        )
        .join(Job, Application.job_id == Job.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Application.candidate_id == current_user.id)
    )

    if status_filter != "all":
        base = base.where(Application.status == status_filter)

    keyword = q.strip()
    if keyword:
        base = base.where(
            Job.title.ilike(f"%{keyword}%") | Company.name.ilike(f"%{keyword}%")
        )

    total_stmt = select(func.count()).select_from(base.subquery())
    total = db.scalar(total_stmt) or 0

    if sort == "updated":
        base = base.order_by(Application.updated_at.desc())
    else:
        base = base.order_by(Application.created_at.desc())

    rows = db.execute(base.offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for r in rows:
        meta = sm.get(r.status)
        iv = None
        if r.interview_at:
            iv = InterviewInfo(
                interview_at=r.interview_at,
                interview_mode=r.interview_mode,
                interview_location=r.interview_location,
            )
        items.append(ApplicationCardOut(
            id=r.id,
            job=_job_summary(r),
            cv_id=r.cv_id,
            cv_name=r.cv_name_snapshot,
            cover_letter=r.cover_letter,
            status=r.status,
            status_label=meta.name if meta else r.status,
            status_tone=meta.tone if meta else "neutral",
            created_at=r.created_at,
            updated_at=r.updated_at,
            interview=iv,
            allowed_actions=_actions(r.status, sm),
        ))

    return ApplicationListOut(items=items, tabs=tabs, total=total, page=page, page_size=page_size)

