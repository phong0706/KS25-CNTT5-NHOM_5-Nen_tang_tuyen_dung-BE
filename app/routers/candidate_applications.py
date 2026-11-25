"""Router ứng tuyển: nộp hồ sơ, danh sách, chi tiết, rút hồ sơ, nháp thư, mẫu thư."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.application import (
    Application,
    ApplicationDraft,
    ApplicationStatusHistory,
    CoverLetterTemplate,
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
    DraftOut,
    DraftSaveRequest,
    InterviewInfo,
    StatusHistoryItem,
    WithdrawReasonOut,
    WithdrawRequest,
)

router = APIRouter(tags=["Candidate Applications"])


def _status_map(db: Session) -> dict[str, MetaApplicationStatus]:
    rows = db.scalars(select(MetaApplicationStatus)).all()
    return {r.slug: r for r in rows}


def _build_job_summary(job_row) -> AppJobSummary:
    logo = getattr(job_row, "company_logo", None)
    logo_2x = getattr(job_row, "company_logo_2x", None)
    ver = getattr(job_row, "company_logo_version", None)
    if logo and ver:
        logo = f"{logo}?v={ver}"
    if logo_2x and ver:
        logo_2x = f"{logo_2x}?v={ver}"
    return AppJobSummary(
        id=job_row.id,
        title=job_row.title,
        company_slug=getattr(job_row, "company_slug", None),
        company_name=job_row.company_name,
        company_logo=logo,
        company_logo_2x=logo_2x,
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

