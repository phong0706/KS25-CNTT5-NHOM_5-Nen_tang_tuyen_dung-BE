"""Router Quản lý ứng viên & Lịch phỏng vấn cho Nhà tuyển dụng (/api/employer/applications).
Quy tắc: Kiểm tra quyền backend (401/403/404), < 200 dòng.
"""
import json
import os
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.employer_scope import EmployerScope, get_employer_scope
from app.crud.application import get_status_history_by_application
from app.db.session import get_db
from app.models.application import (
    Application, ApplicationNote, ApplicationStatus, ApplicationStatusHistory, CV, Interview,
    MetaApplicationStatus, MetaRejectionReason,
)
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.schemas.application import AppTabOut, InterviewInfo, StatusHistoryItem
from app.schemas.employer_application import (
    ApplicantCandidateOut, ApplicantJobOut, ApplicationNoteCreateIn,
    ApplicationNoteOut, BulkRejectApplicationsIn, BulkRejectItemResult, BulkRejectOut,
    EmployerApplicationDetailOut, EmployerApplicationItemOut, EmployerApplicationListOut,
    EmployerInterviewScheduleIn, EmployerStatusUpdateIn, RejectApplicationIn,
)
from app.services.application_reject_service import reject_application_core, validate_rejection_reason
from app.services.cv_service import get_cv_file_path
from app.services.interview_service import check_interview_overlap
from app.services.matching import compute_job_match
from app.services.notification import notify_application_status_changed, notify_interview

router = APIRouter(prefix="/employer/applications", tags=["Employer Applications"])

ALLOWED_TRANSITIONS = {
    ApplicationStatus.SUBMITTED: (ApplicationStatus.REVIEWING, ApplicationStatus.REJECTED),
    ApplicationStatus.REVIEWING: (ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED),
    ApplicationStatus.INTERVIEW: (ApplicationStatus.OFFERED, ApplicationStatus.REJECTED),
}

def _normalize_status(status: str) -> str:
    status = status.strip().upper()
    return ApplicationStatus.REVIEWING.value if status == "SCREENING" else status


def _legacy_status(status: str) -> str:
    return "screening" if status == ApplicationStatus.REVIEWING else status.lower()


def _stored_status(status: str, previous: str) -> str:
    return _legacy_status(status) if previous.islower() else status


def _company_job_ids(company_id: int):
    return select(Job.id).where(Job.company_id == company_id, Job.deleted_at.is_(None))


def _company_application(app_id: int, company_id: int):
    return select(Application).where(
        Application.id == app_id, Application.job_id.in_(_company_job_ids(company_id)),
    )


def _candidate_user_id(db: Session, application: Application) -> int | None:
    if application.candidate_id is not None:
        return application.candidate_id
    return db.scalar(select(CandidateProfile.user_id).where(CandidateProfile.id == application.candidate_profile_id))


def _candidate_profile_join():
    return or_(
        CandidateProfile.user_id == Application.candidate_id,
        and_(
            Application.candidate_id.is_(None),
            CandidateProfile.id == Application.candidate_profile_id,
        ),
    )


def _smap(db: Session) -> dict[str, MetaApplicationStatus]:
    return {r.slug: r for r in db.scalars(select(MetaApplicationStatus)).all()}

def _status_meta(status: str, statuses: dict[str, MetaApplicationStatus]) -> tuple[str, str]:
    normalized = _normalize_status(status)
    meta = (
        statuses.get(status) or statuses.get(_legacy_status(normalized))
        or statuses.get(normalized.lower()) or statuses.get(normalized)
    )
    return (meta.name, meta.tone) if meta else (status, "neutral")


def _iv_info(app_row) -> InterviewInfo | None:
    if not app_row.interview_at:
        return None
    return InterviewInfo(
        interview_at=app_row.interview_at,
        interview_mode=app_row.interview_mode,
        interview_location=app_row.interview_location,
    )

def _calc_match_score(job_obj_or_skills, cand_prof_or_skills) -> int:
    if isinstance(cand_prof_or_skills, dict):
        cand_dict = cand_prof_or_skills
    elif hasattr(cand_prof_or_skills, "skills_json"):
        prof = cand_prof_or_skills
        c_skills = []
        if prof and prof.skills_json:
            try:
                parsed = json.loads(prof.skills_json)
                c_skills = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                c_skills = [s.strip() for s in str(prof.skills_json).split(",") if s.strip()]
        cand_dict = {
            "skills": c_skills,
            "level": prof.level if prof else None,
            "headline": prof.headline if prof else None,
            "location": (prof.location or prof.address) if prof else None,
            "work_type": prof.work_type if prof else None,
            "expected_salary": (prof.expected_salary or prof.desired_salary) if prof else None,
        }
    else:
        c_skills = cand_prof_or_skills if isinstance(cand_prof_or_skills, list) else []
        if isinstance(cand_prof_or_skills, str):
            try:
                parsed = json.loads(cand_prof_or_skills)
                c_skills = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                c_skills = [s.strip() for s in cand_prof_or_skills.split(",") if s.strip()]
        cand_dict = {"skills": c_skills}

    if isinstance(job_obj_or_skills, dict):
        job_dict = job_obj_or_skills
    elif hasattr(job_obj_or_skills, "skills"):
        job = job_obj_or_skills
        j_skills = job.skills if isinstance(job.skills, list) else []
        if not j_skills and isinstance(job.skills, str):
            try:
                parsed = json.loads(job.skills)
                j_skills = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                j_skills = [s.strip() for s in str(job.skills).split(",") if s.strip()]
        job_dict = {
            "skills": j_skills,
            "level": job.level,
            "location": job.location,
            "work_type": job.work_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "is_salary_negotiable": bool(job.is_salary_negotiable),
        }
    else:
        j_skills = job_obj_or_skills if isinstance(job_obj_or_skills, list) else []
        if isinstance(job_obj_or_skills, str):
            try:
                parsed = json.loads(job_obj_or_skills)
                j_skills = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                j_skills = [s.strip() for s in job_obj_or_skills.split(",") if s.strip()]
        job_dict = {"skills": j_skills}

    return compute_job_match(cand_dict, job_dict)["match_score"]

@router.get("/unviewed-count", summary="Số lượng hồ sơ chưa xem")
def get_unviewed_count(
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    count = db.scalar(
        select(func.count(Application.id))
        .where(Application.job_id.in_(_company_job_ids(scope.company_id)), Application.viewed_at.is_(None))
    ) or 0
    return {"count": count}

@router.get("", response_model=EmployerApplicationListOut, summary="Danh sách ứng viên nộp hồ sơ")
def list_employer_applications(
    job_id: int | None = Query(None),
    status_filter: str = Query("all", alias="status"),
    q: str = Query("", max_length=100),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    company_job_ids = _company_job_ids(scope.company_id)
    my_jobs_rows = db.execute(
        select(Job.id, Job.title).where(Job.id.in_(company_job_ids)).order_by(Job.created_at.desc())
    ).all()
    my_jobs = [ApplicantJobOut(id=r.id, title=r.title) for r in my_jobs_rows]
    if job_id is not None and all(job.id != job_id for job in my_jobs):
        raise HTTPException(status_code=404, detail="Không tìm thấy tin tuyển dụng của công ty.")

    if not my_jobs:
        return EmployerApplicationListOut(
            items=[], tabs=[AppTabOut(key="all", label="Tất cả", count=0)], jobs=[], total=0, page=page, page_size=page_size
        )

    scope = [Application.job_id.in_(company_job_ids)]
    if job_id is not None:
        scope.append(Application.job_id == job_id)

    sm = _smap(db)
    count_q = select(Application.status, func.count(Application.id)).where(*scope).group_by(Application.status)
    counts = Counter()
    for app_status, count in db.execute(count_q):
        counts[_normalize_status(app_status)] += count
    tabs = [AppTabOut(key="all", label="Tất cả", count=sum(counts.values()))]
    for meta in sorted(sm.values(), key=lambda m: m.sort_order):
        tabs.append(AppTabOut(key=meta.slug, label=meta.name, count=counts[_normalize_status(meta.slug)]))

    base = (
        select(Application, Job, User, CandidateProfile)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(CandidateProfile, _candidate_profile_join())
        .join(User, User.id == func.coalesce(Application.candidate_id, CandidateProfile.user_id))
        .where(*scope)
    )
    normalized_filter = _normalize_status(status_filter)
    if normalized_filter and normalized_filter != "ALL":
        status_aliases = (normalized_filter.lower(), _legacy_status(normalized_filter))
        base = base.where(func.lower(Application.status).in_(status_aliases))
    if q.strip():
        kw = q.strip()
        base = base.where(User.full_name.ilike(f"%{kw}%") | User.email.ilike(f"%{kw}%") | Job.title.ilike(f"%{kw}%"))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    all_rows = db.execute(base.order_by(Application.created_at.desc(), Application.id.desc())).all()

    items = []
    for app_row, job, cand, prof in all_rows:
        status_label, status_tone = _status_meta(app_row.status, sm)
        items.append(EmployerApplicationItemOut(
            id=app_row.id, job=ApplicantJobOut(id=app_row.job_id, title=job.title),
            candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url),
            cv_id=app_row.cv_id, cv_name=app_row.cv_name_snapshot, cover_letter=app_row.cover_letter,
            status=app_row.status, status_label=status_label, status_tone=status_tone,
            is_viewed=bool(app_row.viewed_at is not None),
            match_score=_calc_match_score(job, prof),
            created_at=app_row.created_at, updated_at=app_row.updated_at, interview=_iv_info(app_row),
        ))

    if sort == "match_score":
        items.sort(key=lambda x: (x.match_score, x.created_at), reverse=True)

    start = (page - 1) * page_size
    paged_items = items[start: start + page_size]
    return EmployerApplicationListOut(items=paged_items, tabs=tabs, jobs=my_jobs, total=total, page=page, page_size=page_size)

@router.get("/{app_id}", response_model=EmployerApplicationDetailOut, summary="Chi tiết hồ sơ ứng viên")
def get_employer_application_detail(
    app_id: int, scope: EmployerScope = Depends(get_employer_scope), db: Session = Depends(get_db),
):
    row = db.execute(
        select(
            Application, Job, Company.slug.label("comp_slug"), Company.name.label("comp_name"), User,
            CandidateProfile,
        )
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .outerjoin(CandidateProfile, _candidate_profile_join())
        .join(User, User.id == func.coalesce(Application.candidate_id, CandidateProfile.user_id))
        .where(Application.id == app_id, Job.company_id == scope.company_id, Job.deleted_at.is_(None))
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại hoặc không thuộc quyền quản lý.")

    app_row, job, c_slug, c_name, cand, prof = row
    sm = _smap(db)
    history = []
    for entry in get_status_history_by_application(db, app_id):
        status = entry.status or entry.new_status
        if status:
            label, tone = _status_meta(status, sm)
            history.append(StatusHistoryItem(
                status=status, status_label=label, status_tone=tone, note=entry.note, changed_at=entry.changed_at,
            ))
    status_label, status_tone = _status_meta(app_row.status, sm)
    allowed = ALLOWED_TRANSITIONS.get(_normalize_status(app_row.status), ())

    return EmployerApplicationDetailOut(
        id=app_row.id, job=ApplicantJobOut(id=app_row.job_id, title=job.title, company_slug=c_slug, company_name=c_name),
        candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url, public_id=prof.public_id if prof else None),
        cv_id=app_row.cv_id, cv_name=app_row.cv_name_snapshot, cover_letter=app_row.cover_letter,
        status=app_row.status, status_label=status_label, status_tone=status_tone,
        is_viewed=bool(app_row.viewed_at is not None),
        match_score=_calc_match_score(job, prof),
        created_at=app_row.created_at, updated_at=app_row.updated_at, interview=_iv_info(app_row), history=history,
        allowed_transitions=[_stored_status(status, app_row.status) for status in allowed],
    )



@router.get("/{app_id}/cv", summary="Xem / tải file CV của đơn ứng tuyển")
def get_application_cv_file(
    app_id: int,
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(Application, Job.company_id)
        .join(Job, Application.job_id == Job.id)
        .where(Application.id == app_id, Job.deleted_at.is_(None))
    ).first()
    if not row or row[1] != scope.company_id:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

    app_row = row[0]

    if not app_row.cv_id:
        raise HTTPException(status_code=404, detail="Đơn ứng tuyển này không có file CV đính kèm.")

    cv = db.scalar(select(CV).where(CV.id == app_row.cv_id))
    if not cv or not cv.stored_name:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin file CV trong hệ thống.")

    filepath = get_cv_file_path(cv.stored_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File CV không tồn tại trên hệ thống lưu trữ.")

    filename = app_row.cv_name_snapshot or cv.original_name or "CV.pdf"
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == ".doc":
        media_type = "application/msword"
    else:
        media_type = cv.mime_type or "application/pdf"

    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers={
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Type",
        },
    )


@router.post("/{app_id}/view", summary="Đánh dấu đã xem hồ sơ")
def mark_application_viewed(
    app_id: int, scope: EmployerScope = Depends(get_employer_scope), db: Session = Depends(get_db),
):
    app = db.scalar(_company_application(app_id, scope.company_id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    if app.viewed_at is None:
        app.viewed_at = datetime.now(timezone.utc)
        db.commit()
    return {"message": "Đã đánh dấu xem hồ sơ", "viewed_at": app.viewed_at}

@router.get("/{app_id}/notes", response_model=list[ApplicationNoteOut], summary="Danh sách ghi chú nội bộ")
def list_application_notes(
    app_id: int, scope: EmployerScope = Depends(get_employer_scope), db: Session = Depends(get_db),
):
    app = db.scalar(_company_application(app_id, scope.company_id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    rows = db.execute(
        select(ApplicationNote, User.full_name).join(User, ApplicationNote.author_id == User.id).where(ApplicationNote.application_id == app_id).order_by(ApplicationNote.created_at.asc())
    ).all()
    return [
        ApplicationNoteOut(id=n.id, application_id=n.application_id, author_id=n.author_id, author_name=name or "Nhà tuyển dụng", content=n.content, created_at=n.created_at)
        for n, name in rows
    ]

@router.post("/{app_id}/notes", response_model=ApplicationNoteOut, summary="Thêm ghi chú nội bộ")
def add_application_note(
    app_id: int, body: ApplicationNoteCreateIn, scope: EmployerScope = Depends(get_employer_scope), db: Session = Depends(get_db),
):
    app = db.scalar(_company_application(app_id, scope.company_id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    note = ApplicationNote(application_id=app.id, author_id=scope.user_id, content=body.content.strip())
    db.add(note)
    db.commit()
    db.refresh(note)
    return ApplicationNoteOut(id=note.id, application_id=note.application_id, author_id=note.author_id, author_name=scope.user.full_name or "Nhà tuyển dụng", content=note.content, created_at=note.created_at)

@router.patch("/{app_id}/status", summary="Cập nhật trạng thái hồ sơ")
def update_application_status(
    app_id: int, body: EmployerStatusUpdateIn, scope: EmployerScope = Depends(get_employer_scope), db: Session = Depends(get_db),
):
    app = db.scalar(_company_application(app_id, scope.company_id).with_for_update())
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

    target = _normalize_status(body.status)
    if target not in {status.value for status in ApplicationStatus}:
        raise HTTPException(status_code=422, detail="Trạng thái không hợp lệ.")

    if target == ApplicationStatus.REJECTED:
        reason = validate_rejection_reason(db, body.rejection_reason_slug or "")
        res = reject_application_core(db, app, scope.user_id, reason, body.note)
        db.commit()
        return {"message": res["message"], "status": res["status"]}

    old_status = app.status
    new_status = _stored_status(target, old_status)
    sm = _smap(db)
    target_label, _ = _status_meta(new_status, sm)
    if target not in ALLOWED_TRANSITIONS.get(_normalize_status(old_status), ()):
        current_label, _ = _status_meta(old_status, sm)
        raise HTTPException(
            status_code=409,
            detail=f"Không thể chuyển từ trạng thái '{current_label}' sang '{target_label}' theo quy trình tuyển dụng.",
        )

    note_text = body.note
    if target == ApplicationStatus.REJECTED and body.rejection_reason_slug:
        reason_row = db.scalar(select(MetaRejectionReason).where(MetaRejectionReason.slug == body.rejection_reason_slug))
        if reason_row:
            rejection_note = f"Lý do từ chối: {reason_row.name}. " + (body.note or "")
            if len(rejection_note) <= 500:
                note_text = rejection_note
    if not note_text:
        note_text = f"Nhà tuyển dụng chuyển trạng thái thành: {target_label}"

    candidate_id = _candidate_user_id(db, app)
    job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
    app.status = new_status
    app.updated_at = datetime.now(timezone.utc)
    if body.note is not None:
        app.employer_notes = body.note
    db.add(ApplicationStatusHistory(
        application_id=app.id, status=new_status, old_status=old_status, new_status=new_status,
        changed_by_user_id=scope.user_id, note=note_text,
    ))
    notification = None
    if candidate_id is not None:
        notification = notify_application_status_changed(
            db, candidate_id=candidate_id, status=new_status, status_label=target_label,
            job_title=job_title, application_id=app.id, actor_id=scope.user_id, note=body.note,
        )
    if notification is None:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể gửi thông báo cập nhật hồ sơ cho ứng viên.")
    db.commit()
    return {"message": "Cập nhật trạng thái hồ sơ thành công!", "status": new_status}

@router.post("/{app_id}/interview", summary="Lên lịch hẹn phỏng vấn")
def schedule_interview(
    app_id: int, body: EmployerInterviewScheduleIn, scope: EmployerScope = Depends(get_employer_scope), db: Session = Depends(get_db),
):
    app = db.scalar(_company_application(app_id, scope.company_id).with_for_update())
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

    old_status = app.status
    current_status = _normalize_status(old_status)
    allowed = ALLOWED_TRANSITIONS.get(current_status, ())
    if current_status != ApplicationStatus.INTERVIEW and ApplicationStatus.INTERVIEW not in allowed:
        current_name, _ = _status_meta(old_status, _smap(db))
        raise HTTPException(status_code=409, detail=f"Không thể lên lịch phỏng vấn cho hồ sơ đang ở trạng thái '{current_name}'.")

    if not body.force:
        overlap = check_interview_overlap(db, scope.user_id, body.scheduled_at, body.duration_min)
        if overlap:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Trùng lịch phỏng vấn",
                    "conflict": {
                        "id": overlap["id"],
                        "scheduled_at": overlap["scheduled_at"].isoformat() if hasattr(overlap["scheduled_at"], "isoformat") else str(overlap["scheduled_at"]),
                        "duration_min": overlap["duration_min"],
                        "candidate_name": overlap["candidate_name"],
                        "job_title": overlap["job_title"],
                    },
                },
            )

    iv = Interview(
        application_id=app.id,
        scheduled_at=body.scheduled_at,
        duration_min=body.duration_min,
        mode=body.mode,
        location_or_link=body.location_or_link,
        interviewer=body.interviewer,
        note=body.note,
        status="scheduled",
        created_by=scope.user_id,
    )
    db.add(iv)

    app.interview_at = body.scheduled_at
    app.interview_mode = body.mode
    app.interview_location = body.location_or_link
    app.status = _stored_status(ApplicationStatus.INTERVIEW.value, old_status)
    app.updated_at = datetime.now(timezone.utc)

    loc_str = f" tại {body.location_or_link}" if body.location_or_link else ""
    note_text = body.note or f"Lên lịch phỏng vấn {body.mode}{loc_str}"
    db.add(ApplicationStatusHistory(
        application_id=app.id, status=app.status, old_status=old_status, new_status=app.status,
        changed_by_user_id=scope.user_id, note=note_text,
    ))

    job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
    notify_interview(
        db, candidate_id=_candidate_user_id(db, app), application_id=app.id, job_title=job_title,
        interview_at=body.scheduled_at, interview_mode=body.mode,
        interview_location=body.location_or_link, actor_id=scope.user_id,
    )
    db.commit()
    return {"message": "Đã lên lịch hẹn phỏng vấn thành công!", "interview_id": iv.id, "scheduled_at": body.scheduled_at}


@router.post("/bulk-reject", response_model=BulkRejectOut, summary="Từ chối hàng loạt hồ sơ")
def bulk_reject_applications(
    body: BulkRejectApplicationsIn,
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    reason = validate_rejection_reason(db, body.reason_code)
    unique_ids = list(dict.fromkeys(body.ids))
    apps = {
        a.id: a
        for a in db.scalars(
            select(Application).where(
                Application.id.in_(unique_ids),
                Application.job_id.in_(_company_job_ids(scope.company_id)),
            ).with_for_update()
        ).all()
    }
    results: list[BulkRejectItemResult] = []
    rejected_count = 0
    skipped_count = 0
    for app_id in unique_ids:
        app = apps.get(app_id)
        if not app:
            skipped_count += 1
            results.append(BulkRejectItemResult(id=app_id, status="skipped", detail="Không tìm thấy hồ sơ"))
            continue
        try:
            res = reject_application_core(db, app, scope.user_id, reason, body.message)
            if res.get("already_rejected"):
                skipped_count += 1
                results.append(BulkRejectItemResult(id=app_id, status="skipped", detail="Đã từ chối trước đó"))
            else:
                rejected_count += 1
                results.append(BulkRejectItemResult(id=app_id, status="rejected", detail="Đã từ chối"))
        except HTTPException as exc:
            skipped_count += 1
            results.append(BulkRejectItemResult(id=app_id, status="skipped", detail=str(exc.detail)))

    db.commit()
    return BulkRejectOut(
        total=len(unique_ids),
        rejected_count=rejected_count,
        skipped_count=skipped_count,
        results=results,
    )


@router.post("/{app_id}/reject", summary="Từ chối hồ sơ ứng viên")
def reject_application(
    app_id: int,
    body: RejectApplicationIn,
    scope: EmployerScope = Depends(get_employer_scope),
    db: Session = Depends(get_db),
):
    reason = validate_rejection_reason(db, body.reason_code)
    app = db.scalar(_company_application(app_id, scope.company_id).with_for_update())
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    res = reject_application_core(db, app, scope.user_id, reason, body.message)
    db.commit()
    return res
