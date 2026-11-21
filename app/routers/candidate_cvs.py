"""Router /candidate/cvs: Quản lý và Tải lên CV cho Ứng viên.

Tuân thủ techrecruit-rules: <= 200 dòng, phân quyền chặt chẽ, magic bytes, bảo mật lưu trữ.
"""
import logging
import os
import time
import uuid
from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.application import Application, CV
from app.models.job import Job
from app.models.user import User
from app.schemas.application import CVOut, CVRenameIn
from app.services.cv_service import (
    CV_STORAGE_DIR,
    MAX_CVS_PER_USER,
    build_cv_response,
    check_duplicate_content,
    ensure_storage_dirs,
    get_cv_file_path,
    sanitize_cv_name,
    validate_cv_content,
)

logger = logging.getLogger("techrecruit.cv")
router = APIRouter(tags=["Candidate CVs"])
IDEMPOTENCY_CACHE: dict[str, tuple[float, CVOut]] = {}
ACTIVE_APP_STATUSES = {"SUBMITTED", "REVIEWING", "INTERVIEW", "OFFERED", "submitted", "reviewing", "interview", "offered"}


def require_candidate(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chức năng chỉ dành cho ứng viên.")
    return current_user


@router.get("/candidate/cvs", response_model=list[CVOut], summary="Danh sách CV của ứng viên")
def list_candidate_cvs(current_user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    cv_list = db.scalars(select(CV).where(CV.candidate_id == current_user.id).order_by(CV.is_default.desc(), CV.created_at.desc())).all()
    results = []
    for cv in cv_list:
        used_cnt = db.scalar(select(func.count(Application.id)).where(Application.cv_id == cv.id)) or 0
        active_cnt = db.scalar(select(func.count(Application.id)).where(Application.cv_id == cv.id, Application.status.in_(ACTIVE_APP_STATUSES))) or 0
        results.append(build_cv_response(cv, used_cnt, active_cnt))
    return results


@router.post("/candidate/cvs", response_model=CVOut, status_code=status.HTTP_201_CREATED, summary="Tải lên CV mới")
async def upload_candidate_cv(
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    if idempotency_key:
        cache_key = f"{current_user.id}:{idempotency_key}"
        cached = IDEMPOTENCY_CACHE.get(cache_key)
        if cached and (time.time() - cached[0] < 60):
            return cached[1]

    # Kiểm tra giới hạn 5 CV/người
    curr_count = db.scalar(select(func.count(CV.id)).where(CV.candidate_id == current_user.id)) or 0
    if curr_count >= MAX_CVS_PER_USER:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bạn đã đạt giới hạn tối đa 5 CV. Vui lòng xóa bớt CV cũ.")

    content = await file.read()
    mime, ext = validate_cv_content(content)
    check_duplicate_content(db, current_user.id, content)

    ensure_storage_dirs()
    stored = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(CV_STORAGE_DIR, stored)
    with open(filepath, "wb") as f:
        f.write(content)

    clean_name = sanitize_cv_name(file.filename or f"CV{ext}")
    cv = CV(
        candidate_id=current_user.id,
        original_name=clean_name,
        stored_name=stored,
        mime_type=mime,
        size_bytes=len(content),
        is_default=(curr_count == 0),
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)

    res_out = build_cv_response(cv, 0, 0)
    if idempotency_key:
        IDEMPOTENCY_CACHE[f"{current_user.id}:{idempotency_key}"] = (time.time(), res_out)
    return res_out


@router.patch("/candidate/cvs/{cv_id}", response_model=CVOut, summary="Đổi tên CV")
def rename_candidate_cv(cv_id: int, payload: CVRenameIn, current_user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    cv = db.scalar(select(CV).where(CV.id == cv_id, CV.candidate_id == current_user.id))
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy CV.")

    ext = os.path.splitext(cv.original_name)[1]
    new_clean = sanitize_cv_name(payload.name)
    if not new_clean.lower().endswith(ext.lower()):
        new_clean = f"{new_clean}{ext}"
    cv.original_name = new_clean
    db.commit()
    db.refresh(cv)

    used_cnt = db.scalar(select(func.count(Application.id)).where(Application.cv_id == cv.id)) or 0
    active_cnt = db.scalar(select(func.count(Application.id)).where(Application.cv_id == cv.id, Application.status.in_(ACTIVE_APP_STATUSES))) or 0
    return build_cv_response(cv, used_cnt, active_cnt)


@router.post("/candidate/cvs/{cv_id}/default", response_model=CVOut, summary="Đặt CV làm mặc định")
def set_default_candidate_cv(cv_id: int, current_user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    cv = db.scalar(select(CV).where(CV.id == cv_id, CV.candidate_id == current_user.id))
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy CV.")

    all_cvs = db.scalars(select(CV).where(CV.candidate_id == current_user.id)).all()
    for c in all_cvs:
        c.is_default = (c.id == cv.id)
    db.commit()
    db.refresh(cv)

    used_cnt = db.scalar(select(func.count(Application.id)).where(Application.cv_id == cv.id)) or 0
    active_cnt = db.scalar(select(func.count(Application.id)).where(Application.cv_id == cv.id, Application.status.in_(ACTIVE_APP_STATUSES))) or 0
    return build_cv_response(cv, used_cnt, active_cnt)


@router.get("/candidate/cvs/{cv_id}/file", summary="Xem / tải file CV có kiểm tra quyền sở hữu")
def get_candidate_cv_file(cv_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cv = db.scalar(select(CV).where(CV.id == cv_id))
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy CV.")

    if current_user.role == "candidate":
        if cv.candidate_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy CV.")
    elif current_user.role in ("employer", "recruiter"):
        has_app = db.scalar(select(Application.id).join(Job, Application.job_id == Job.id).where(Application.cv_id == cv.id, Job.employer_id == current_user.id))
        if not has_app:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập CV này.")
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập CV này.")

    filepath = get_cv_file_path(cv.stored_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File CV không tồn tại trên hệ thống lưu trữ.")

    disposition = "inline" if cv.mime_type == "application/pdf" else "attachment"
    clean_disp_name = cv.original_name.encode("ascii", "ignore").decode("ascii") or "cv_download"
    return FileResponse(
        filepath,
        media_type=cv.mime_type,
        filename=cv.original_name,
        headers={
            "Content-Disposition": f'{disposition}; filename="{clean_disp_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/candidate/cvs/{cv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa CV")
def delete_candidate_cv(cv_id: int, current_user: User = Depends(require_candidate), db: Session = Depends(get_db)):
    cv = db.scalar(select(CV).where(CV.id == cv_id, CV.candidate_id == current_user.id))
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy CV.")

    active_apps = db.scalars(select(Application).where(Application.cv_id == cv.id, Application.status.in_(ACTIVE_APP_STATUSES))).all()
    if active_apps:
        job_ids = [a.job_id for a in active_apps if a.job_id]
        jobs = db.scalars(select(Job).where(Job.id.in_(job_ids))).all()
        job_titles = [j.title for j in jobs]
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": "Không thể xóa CV đang được sử dụng trong các hồ sơ ứng tuyển.", "active_jobs": job_titles})

    was_default = cv.is_default
    filepath = get_cv_file_path(cv.stored_name)
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.warning("Không thể xóa file vật lý CV %s: %s", filepath, e)

    db.delete(cv)
    if was_default:
        next_cv = db.scalar(select(CV).where(CV.candidate_id == current_user.id, CV.id != cv.id).order_by(CV.created_at.desc()))
        if next_cv:
            next_cv.is_default = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
