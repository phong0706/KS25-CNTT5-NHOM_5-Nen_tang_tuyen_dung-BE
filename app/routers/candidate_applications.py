"""Router ứng tuyển: CV, nộp hồ sơ, danh sách, chi tiết, rút hồ sơ, nháp thư, mẫu thư."""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM, _bearer, get_current_user, role_required
from app.db.session import get_db
from app.models.application import (
    Application,
    ApplicationDraft,
    ApplicationStatusHistory,
    CoverLetterTemplate,
    CV,
    MetaApplicationStatus,
    MetaWithdrawReason,
)
from app.models.job import Job
from app.models.company import Company
from app.schemas.application import (
    AppAllowedAction,
    ApplicationCardOut,
    ApplicationDetailOut,
    ApplicationListOut,
    AppJobSummary,
    AppStatusMeta,
    AppTabOut,
    ApplyOut,
    ApplyRequest,
    CoverLetterTemplateOut,
    CVOut,
    DraftOut,
    DraftSaveRequest,
    InterviewInfo,
    StatusHistoryItem,
    WithdrawReasonOut,
    WithdrawRequest,
)

router = APIRouter(tags=["Candidate Applications"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "cvs")
ALLOWED_MIME = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_CV_SIZE = 5 * 1024 * 1024  # 5 MB


def _status_map(db: Session) -> dict[str, MetaApplicationStatus]:
    rows = db.scalars(select(MetaApplicationStatus)).all()
    return {r.slug: r for r in rows}


def _build_job_summary(job_row) -> AppJobSummary:
    return AppJobSummary(
        id=job_row.id,
        title=job_row.title,
        company_name=job_row.company_name,
        location=job_row.location,
        salary_min=job_row.salary_min,
        salary_max=job_row.salary_max,
        is_salary_negotiable=job_row.is_salary_negotiable,
        work_type=job_row.work_type,
        status=job_row.job_status,
    )


def _allowed_actions(app_status: str, smap: dict) -> list[AppAllowedAction]:
    meta = smap.get(app_status)
    actions: list[AppAllowedAction] = [AppAllowedAction(key="view_job", label="Xem tin")]
    actions.append(AppAllowedAction(key="view_cv", label="Xem CV"))
    if meta and not meta.is_terminal:
        actions.append(AppAllowedAction(key="withdraw", label="Rút hồ sơ"))
    return actions


# ── META ──────────────────────────────────────────────────────

@router.get(
    "/meta/application-statuses",
    response_model=list[AppStatusMeta],
    summary="Danh sách trạng thái ứng tuyển",
)
def list_app_statuses(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(MetaApplicationStatus).order_by(MetaApplicationStatus.sort_order)
    ).all()
    return rows


@router.get(
    "/meta/withdraw-reasons",
    response_model=list[WithdrawReasonOut],
    summary="Danh sách lý do rút hồ sơ",
)
def list_withdraw_reasons(db: Session = Depends(get_db)):
    return db.scalars(
        select(MetaWithdrawReason).order_by(MetaWithdrawReason.sort_order)
    ).all()


# ── CVs ───────────────────────────────────────────────────────

@router.get("/candidate/cvs", response_model=list[CVOut], summary="Danh sách CV của ứng viên")
def list_cvs(current_user=Depends(role_required("candidate")), db: Session = Depends(get_db)):
    return db.scalars(
        select(CV)
        .where(CV.candidate_id == current_user.id)
        .order_by(CV.is_default.desc(), CV.created_at.desc())
    ).all()


@router.post(
    "/candidate/cvs",
    response_model=CVOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tải lên CV mới",
)
async def upload_cv(
    file: UploadFile = File(...),
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    # Kiểm tra MIME thật
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chỉ chấp nhận file PDF, DOC hoặc DOCX.",
        )

    content = await file.read()
    if len(content) > MAX_CV_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dung lượng file vượt quá 5 MB.",
        )

    # Kiểm tra magic bytes
    is_pdf = content[:5] == b"%PDF-"
    is_docx = content[:4] == b"PK\x03\x04"
    is_doc = content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    if not (is_pdf or is_docx or is_doc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nội dung file không hợp lệ. Chỉ chấp nhận PDF, DOC hoặc DOCX.",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "cv")[1] or ".pdf"
    stored = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, stored)
    with open(filepath, "wb") as f:
        f.write(content)

    # Nếu chưa có CV nào thì đặt mặc định
    has_cv = db.scalar(select(func.count(CV.id)).where(CV.candidate_id == current_user.id))
    cv = CV(
        candidate_id=current_user.id,
        original_name=file.filename or "CV.pdf",
        stored_name=stored,
        mime_type=file.content_type,
        size_bytes=len(content),
        is_default=(has_cv == 0),
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


@router.delete("/candidate/cvs/{cv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa CV")
def delete_cv(
    cv_id: int,
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    cv = db.scalar(select(CV).where(CV.id == cv_id, CV.candidate_id == current_user.id))
    if not cv:
        raise HTTPException(status_code=404, detail="CV không tồn tại.")
    filepath = os.path.join(UPLOAD_DIR, cv.stored_name)
    if os.path.isfile(filepath):
        os.remove(filepath)
    db.delete(cv)
    db.commit()


@router.get("/candidate/cvs/{cv_id}/file", summary="Xem / tải file CV")
def get_cv_file(
    cv_id: int,
    token: str | None = Query(None),
    auth_header=Depends(_bearer),
    db: Session = Depends(get_db),
):
    raw_token = auth_header.credentials if auth_header else token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để xem file.")
    try:
        payload = jwt.decode(raw_token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", 0))
        role = str(payload.get("role", ""))
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ.")

    cv = db.scalar(select(CV).where(CV.id == cv_id))
    if not cv:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV.")

    can_view = (cv.candidate_id == user_id) or (role == "admin")
    if not can_view and role in ("recruiter", "employer"):
        has_app = db.scalar(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(Application.cv_id == cv_id, Job.employer_id == user_id)
        )
        if has_app:
            can_view = True

    if not can_view:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập CV này.")

    filepath = os.path.join(UPLOAD_DIR, cv.stored_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File CV không tồn tại trên hệ thống lưu trữ.")

    return FileResponse(
        filepath,
        media_type=cv.mime_type,
        filename=cv.original_name,
        headers={"Content-Disposition": f'inline; filename="{cv.original_name}"'},
    )


# ── COVER LETTER ──────────────────────────────────────────────

@router.get(
    "/candidate/cover-letter-templates",
    response_model=list[CoverLetterTemplateOut],
    summary="Mẫu thư giới thiệu",
)
def list_templates(db: Session = Depends(get_db)):
    return db.scalars(
        select(CoverLetterTemplate).order_by(CoverLetterTemplate.sort_order)
    ).all()


@router.get("/candidate/cover-letter-draft/{job_id}", response_model=DraftOut | None)
def get_draft(
    job_id: int,
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    draft = db.scalar(
        select(ApplicationDraft).where(
            ApplicationDraft.candidate_id == current_user.id,
            ApplicationDraft.job_id == job_id,
        )
    )
    if not draft:
        return None
    return DraftOut(cover_letter=draft.cover_letter, updated_at=draft.updated_at)


@router.put("/candidate/cover-letter-draft/{job_id}", response_model=DraftOut)
def save_draft(
    job_id: int,
    body: DraftSaveRequest,
    current_user=Depends(role_required("candidate")),
    db: Session = Depends(get_db),
):
    draft = db.scalar(
        select(ApplicationDraft).where(
            ApplicationDraft.candidate_id == current_user.id,
            ApplicationDraft.job_id == job_id,
        )
    )
    now = datetime.now(timezone.utc)
    if draft:
        draft.cover_letter = body.cover_letter
        draft.updated_at = now
    else:
        draft = ApplicationDraft(
            candidate_id=current_user.id,
            job_id=job_id,
            cover_letter=body.cover_letter,
            updated_at=now,
        )
        db.add(draft)
    db.commit()
    db.refresh(draft)
    return DraftOut(cover_letter=draft.cover_letter, updated_at=draft.updated_at)

