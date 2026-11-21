"""Router hồ sơ ứng viên dành cho nhà tuyển dụng (/api/employer/candidates).
Tuân thủ techrecruit-rules: whitelist serializer, kiểm quyền backend, < 200 dòng.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.application import Application, CV
from app.models.candidate import CandidateProfile
from app.models.candidate_profile import CandidateEducation, CandidateExperience
from app.models.company import Company
from app.models.job import Job
from app.models.profile_view import ProfileView
from app.models.user import User
from app.services.matching import compute_job_match
from app.services.profile_access import (
    build_candidate_profile_payload,
    profile_view_rate_limiter,
    record_profile_view_if_needed,
    resolve_profile_access,
)

router = APIRouter(tags=["Employer Candidate Profile"])

CV_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "cvs"
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


@router.get("/employer/candidates/{public_id}", summary="Xem hồ sơ ứng viên bằng mã public_id")
def get_employer_candidate_profile(
    public_id: str,
    job_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed, retry_after = profile_view_rate_limiter.check_and_record(current_user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Bạn đã gửi quá nhiều yêu cầu. Giới hạn 60 lượt/phút.",
            headers={"Retry-After": str(retry_after)},
        )

    if not ID_PATTERN.match(public_id or ""):
        raise HTTPException(status_code=404, detail="Hồ sơ ứng viên không tồn tại hoặc không khả dụng.")

    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.public_id == public_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng viên không tồn tại hoặc không khả dụng.")

    cand_user = db.scalar(select(User).where(User.id == profile.user_id))
    if not cand_user or not cand_user.is_active:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng viên không tồn tại hoặc không khả dụng.")

    job_obj = None
    if job_id is not None:
        job_row = db.execute(
            select(Job, Company.employer_id).outerjoin(Company, Job.company_id == Company.id).where(Job.id == job_id)
        ).first()
        if not job_row:
            raise HTTPException(status_code=404, detail="Tin tuyển dụng không tồn tại.")
        job_obj, comp_owner_id = job_row[0], job_row[1]
        if current_user.role != "admin" and job_obj.employer_id != current_user.id and comp_owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Tin tuyển dụng không thuộc quyền quản lý của bạn.")

    emp_subq = select(Job.id).outerjoin(Company, Job.company_id == Company.id).where(
        or_(Job.employer_id == current_user.id, Company.employer_id == current_user.id)
    )
    if current_user.role == "admin":
        emp_apps = list(db.scalars(select(Application).where(Application.candidate_id == cand_user.id)).all())
    else:
        emp_apps = list(db.scalars(select(Application).where(
            Application.candidate_id == cand_user.id, Application.job_id.in_(emp_subq)
        )).all())

    try:
        access = resolve_profile_access(current_user, profile, emp_apps)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Ứng viên không có quyền xem hồ sơ của ứng viên khác.")

    if access == "none":
        raise HTTPException(status_code=404, detail="Hồ sơ ứng viên không tồn tại hoặc không khả dụng.")

    record_profile_view_if_needed(db, current_user.id, cand_user.id, emp_apps, job_id)

    raw_skills = []
    if profile.skills_json:
        try:
            raw_skills = json.loads(profile.skills_json)
        except Exception:
            pass
    if not raw_skills and profile.skills:
        raw_skills = [s.skill_name for s in profile.skills]

    exps = list(db.scalars(select(CandidateExperience).where(CandidateExperience.user_id == cand_user.id).order_by(CandidateExperience.start_month.desc())).all())
    edus = list(db.scalars(select(CandidateEducation).where(CandidateEducation.user_id == cand_user.id).order_by(CandidateEducation.start_year.desc())).all())

    apps_to_you = None
    if access == "full":
        apps_to_you = [{
            "application_id": a.id, "job_id": a.job_id,
            "job_title": db.scalar(select(Job.title).where(Job.id == a.job_id)) or "",
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "applied_at": a.created_at.isoformat() if a.created_at else None,
            "has_cv": bool(a.cv_id),
        } for a in emp_apps]

    match_data = None
    if job_id and job_obj:
        m = compute_job_match(
            {"skills": raw_skills, "headline": profile.headline, "location": profile.location, "work_type": profile.work_type, "expected_salary": profile.expected_salary or profile.desired_salary},
            {"skills": [s.skill_name for s in (getattr(job_obj, "skills", None) or [])], "level": job_obj.level, "location": job_obj.location, "work_type": job_obj.work_type, "salary_min": job_obj.salary_min, "salary_max": job_obj.salary_max, "is_salary_negotiable": job_obj.is_salary_negotiable},
        )
        match_data = {"score": m["match_score"], "matched_skills": m["matched_skills"], "missing_skills": m["missing_skills"]}

    payload = build_candidate_profile_payload(profile, cand_user, access, raw_skills, exps, edus, apps_to_you, match_data)
    return JSONResponse(content=payload, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/employer/candidates/{public_id}/cv/{application_id}", summary="Tải CV ứng viên cho đơn nộp thuộc tin của employer")
def get_employer_candidate_cv(
    public_id: str,
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not ID_PATTERN.match(public_id or ""):
        raise HTTPException(status_code=404, detail="Không tìm thấy file CV hoặc bạn không có quyền truy cập.")

    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.public_id == public_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Không tìm thấy file CV hoặc bạn không có quyền truy cập.")

    row = db.execute(
        select(Application, Job.employer_id, Company.employer_id)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Application.id == application_id, Application.candidate_id == profile.user_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy file CV hoặc bạn không có quyền truy cập.")

    app_row, job_owner, comp_owner = row[0], row[1], row[2]
    if current_user.role != "admin" and job_owner != current_user.id and comp_owner != current_user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy file CV hoặc bạn không có quyền truy cập.")

    st_str = (app_row.status.value if hasattr(app_row.status, "value") else str(app_row.status or "")).upper()
    if st_str == "WITHDRAWN" or app_row.withdrawn_at is not None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file CV hoặc hồ sơ đã bị rút.")

    if not app_row.cv_id:
        raise HTTPException(status_code=404, detail="Đơn ứng tuyển này không có file CV đính kèm.")

    cv = db.scalar(select(CV).where(CV.id == app_row.cv_id))
    if not cv or not cv.stored_name:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin file CV trong hệ thống.")

    fp = CV_DIR / cv.stored_name
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="File CV không tồn tại trên hệ thống lưu trữ.")

    fn = app_row.cv_name_snapshot or cv.original_name or "CV.pdf"
    mime = "application/pdf" if fp.suffix.lower() == ".pdf" else (cv.mime_type or "application/octet-stream")
    return FileResponse(
        path=str(fp), media_type=mime, filename=fn,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": f'inline; filename="{fn}"'},
    )


@router.get("/candidate/profile/views-summary", summary="Thống kê số lượt xem hồ sơ 30 ngày gần nhất")
def get_candidate_views_summary(
    current_user: User = Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    cnt = db.scalar(
        select(func.count(ProfileView.id)).where(
            ProfileView.candidate_user_id == current_user.id,
            ProfileView.viewed_at >= since,
        )
    ) or 0
    return {"views_30d": int(cnt)}
