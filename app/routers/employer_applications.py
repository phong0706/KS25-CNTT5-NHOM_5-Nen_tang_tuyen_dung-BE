"""Router Quản lý ứng viên & Lịch phỏng vấn cho Nhà tuyển dụng (/api/employer/applications).
Quy tắc: Kiểm tra quyền backend (401/403/404), < 200 dòng.
"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.application import (
    Application, ApplicationNote, ApplicationStatusHistory, CV, Interview,
    MetaApplicationStatus, MetaRejectionReason,
)
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.user import User
from app.schemas.application import AppTabOut, InterviewInfo, StatusHistoryItem
from app.schemas.employer_application import (
    ApplicantCandidateOut, ApplicantJobOut, ApplicationNoteCreateIn,
    ApplicationNoteOut, EmployerApplicationDetailOut,
    EmployerApplicationItemOut, EmployerApplicationListOut,
    EmployerInterviewScheduleIn, EmployerStatusUpdateIn,
)
from app.services.notification import notify_application_status_changed, notify_interview

router = APIRouter(prefix="/employer/applications", tags=["Employer Applications"])

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "submitted": ["screening", "rejected"],
    "screening": ["interview", "rejected"],
    "interview": ["offered", "rejected"],
    "offered": ["rejected"],
    "rejected": [],
    "withdrawn": [],
}

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

def _calc_match_score(job_skills_val, cand_skills_val) -> int:
    if not job_skills_val:
        return 80
    j_skills = job_skills_val if isinstance(job_skills_val, list) else []
    if not j_skills and isinstance(job_skills_val, str):
        try:
            j_skills = json.loads(job_skills_val)
        except Exception:
            j_skills = [s.strip() for s in job_skills_val.split(",") if s.strip()]
    if not j_skills:
        return 80
    c_skills = []
    if cand_skills_val:
        if isinstance(cand_skills_val, list):
            c_skills = cand_skills_val
        elif isinstance(cand_skills_val, str):
            try:
                c_skills = json.loads(cand_skills_val)
            except Exception:
                c_skills = [s.strip() for s in cand_skills_val.split(",") if s.strip()]
    if not c_skills:
        return 65
    j_set = {str(s).strip().lower() for s in j_skills if str(s).strip()}
    c_set = {str(s).strip().lower() for s in c_skills if str(s).strip()}
    if not j_set:
        return 80
    common = j_set.intersection(c_set)
    return int(min(98, max(55, round(60 + (len(common) / len(j_set)) * 38))))

@router.get("/unviewed-count", summary="Số lượng hồ sơ chưa xem")
def get_unviewed_count(
    current_user=Depends(role_required("recruiter", "employer")),
    db: Session = Depends(get_db),
):
    count = db.scalar(
        select(func.count(Application.id))
        .join(Job, Application.job_id == Job.id)
        .where(Job.employer_id == current_user.id, Application.viewed_at.is_(None))
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

    base = (
        select(Application, Job.title.label("job_title"), Job.skills.label("job_skills"), User, CandidateProfile.skills_json)
        .join(Job, Application.job_id == Job.id)
        .join(User, Application.candidate_id == User.id)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == User.id)
        .where(Job.employer_id == current_user.id)
    )
    if job_id and job_id in my_job_ids:
        base = base.where(Application.job_id == job_id)
    if status_filter and status_filter != "all":
        base = base.where(Application.status == status_filter)
    if q.strip():
        kw = q.strip()
        base = base.where(User.full_name.ilike(f"%{kw}%") | User.email.ilike(f"%{kw}%") | Job.title.ilike(f"%{kw}%"))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    all_rows = db.execute(base.order_by(Application.created_at.desc())).all()

    items = [
        EmployerApplicationItemOut(
            id=app_row.id, job=ApplicantJobOut(id=app_row.job_id, title=j_title),
            candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url),
            cv_id=app_row.cv_id, cv_name=app_row.cv_name_snapshot, cover_letter=app_row.cover_letter,
            status=app_row.status, status_label=sm.get(app_row.status).name if sm.get(app_row.status) else app_row.status,
            status_tone=sm.get(app_row.status).tone if sm.get(app_row.status) else "neutral",
            is_viewed=bool(app_row.viewed_at is not None),
            match_score=_calc_match_score(j_skills, c_skills_json),
            created_at=app_row.created_at, updated_at=app_row.updated_at, interview=_iv_info(app_row),
        )
        for app_row, j_title, j_skills, cand, c_skills_json in all_rows
    ]

    if sort == "match_score":
        items.sort(key=lambda x: (x.match_score, x.created_at), reverse=True)

    start = (page - 1) * page_size
    paged_items = items[start: start + page_size]
    return EmployerApplicationListOut(items=paged_items, tabs=tabs, jobs=my_jobs, total=total, page=page, page_size=page_size)

@router.get("/{app_id}", response_model=EmployerApplicationDetailOut, summary="Chi tiết hồ sơ ứng viên")
def get_employer_application_detail(
    app_id: int, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    row = db.execute(
        select(Application, Job.title.label("job_title"), Job.skills.label("job_skills"), User, CandidateProfile.skills_json)
        .join(Job, Application.job_id == Job.id)
        .join(User, Application.candidate_id == User.id)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == User.id)
        .where(Application.id == app_id, Job.employer_id == current_user.id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại hoặc không thuộc quyền quản lý.")

    app_row, j_title, j_skills, cand, c_skills_json = row
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
        is_viewed=bool(app_row.viewed_at is not None),
        match_score=_calc_match_score(j_skills, c_skills_json),
        created_at=app_row.created_at, updated_at=app_row.updated_at, interview=_iv_info(app_row), history=history,
        allowed_transitions=ALLOWED_TRANSITIONS.get(app_row.status, []),
    )


UPLOAD_CV_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "cvs")


@router.get("/{app_id}/cv", summary="Xem / tải file CV của đơn ứng tuyển")
def get_application_cv_file(
    app_id: int,
    current_user=Depends(role_required("recruiter", "employer")),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(Application, Job.employer_id)
        .join(Job, Application.job_id == Job.id)
        .where(Application.id == app_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

    app_row, job_owner_id = row[0], row[1]
    if job_owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền xem CV của đơn ứng tuyển thuộc tin tuyển dụng khác.",
        )

    if not app_row.cv_id:
        raise HTTPException(status_code=404, detail="Đơn ứng tuyển này không có file CV đính kèm.")

    cv = db.scalar(select(CV).where(CV.id == app_row.cv_id))
    if not cv or not cv.stored_name:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin file CV trong hệ thống.")

    filepath = os.path.join(UPLOAD_CV_DIR, cv.stored_name)
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
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Type",
        },
    )


@router.post("/{app_id}/view", summary="Đánh dấu đã xem hồ sơ")
def mark_application_viewed(
    app_id: int, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    app = db.scalar(select(Application).join(Job, Application.job_id == Job.id).where(Application.id == app_id, Job.employer_id == current_user.id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    if app.viewed_at is None:
        app.viewed_at = datetime.now(timezone.utc)
        db.commit()
    return {"message": "Đã đánh dấu xem hồ sơ", "viewed_at": app.viewed_at}

@router.get("/{app_id}/notes", response_model=list[ApplicationNoteOut], summary="Danh sách ghi chú nội bộ")
def list_application_notes(
    app_id: int, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    app = db.scalar(select(Application).join(Job, Application.job_id == Job.id).where(Application.id == app_id, Job.employer_id == current_user.id))
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
    app_id: int, body: ApplicationNoteCreateIn, current_user=Depends(role_required("recruiter", "employer")), db: Session = Depends(get_db),
):
    app = db.scalar(select(Application).join(Job, Application.job_id == Job.id).where(Application.id == app_id, Job.employer_id == current_user.id))
    if not app:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
    note = ApplicationNote(application_id=app.id, author_id=current_user.id, content=body.content.strip())
    db.add(note)
    db.commit()
    db.refresh(note)
    return ApplicationNoteOut(id=note.id, application_id=note.application_id, author_id=note.author_id, author_name=current_user.full_name or "Nhà tuyển dụng", content=note.content, created_at=note.created_at)

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

    allowed = ALLOWED_TRANSITIONS.get(app.status, [])
    if body.status not in allowed:
        current_name = sm.get(app.status).name if sm.get(app.status) else app.status
        target_name = sm.get(body.status).name if sm.get(body.status) else body.status
        raise HTTPException(status_code=409, detail=f"Không thể chuyển từ trạng thái '{current_name}' sang '{target_name}' theo quy trình tuyển dụng.")

    app.status = body.status
    app.updated_at = datetime.now(timezone.utc)

    note_text = body.note
    if body.status == "rejected" and body.rejection_reason_slug:
        reason_row = db.scalar(select(MetaRejectionReason).where(MetaRejectionReason.slug == body.rejection_reason_slug))
        if reason_row:
            note_text = f"Lý do từ chối: {reason_row.name}. " + (body.note or "")
    if not note_text:
        note_text = f"Nhà tuyển dụng chuyển trạng thái thành: {sm[body.status].name}"

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

    allowed = ALLOWED_TRANSITIONS.get(app.status, [])
    if "interview" not in allowed and app.status != "interview":
        sm = _smap(db)
        current_name = sm.get(app.status).name if sm.get(app.status) else app.status
        raise HTTPException(status_code=409, detail=f"Không thể lên lịch phỏng vấn cho hồ sơ đang ở trạng thái '{current_name}'.")

    if not body.force:
        from app.routers.employer_interviews import _check_overlap
        overlap = _check_overlap(db, current_user.id, body.scheduled_at, body.duration_min)
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
        created_by=current_user.id,
    )
    db.add(iv)

    app.interview_at = body.scheduled_at
    app.interview_mode = body.mode
    app.interview_location = body.location_or_link
    app.status = "interview"
    app.updated_at = datetime.now(timezone.utc)

    loc_str = f" tại {body.location_or_link}" if body.location_or_link else ""
    note_text = body.note or f"Lên lịch phỏng vấn {body.mode}{loc_str}"
    db.add(ApplicationStatusHistory(application_id=app.id, status="interview", note=note_text))

    job_title = db.scalar(select(Job.title).where(Job.id == app.job_id)) or ""
    notify_interview(
        db, candidate_id=app.candidate_id, application_id=app.id, job_title=job_title,
        interview_at=body.scheduled_at, interview_mode=body.mode,
        interview_location=body.location_or_link, actor_id=current_user.id,
    )
    db.commit()
    return {"message": "Đã lên lịch hẹn phỏng vấn thành công!", "interview_id": iv.id, "scheduled_at": body.scheduled_at}
