"""Schemas Pydantic cho hồ sơ ứng tuyển, CV, timeline, mẫu thư."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Meta ──────────────────────────────────────────────────────
class AppStatusMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    tone: str
    sort_order: int
    is_terminal: bool


class WithdrawReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str


class CoverLetterTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str


# ── CV ────────────────────────────────────────────────────────
class CVOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_name: str
    mime_type: str
    size_bytes: int
    is_default: bool
    created_at: datetime


# ── Apply ─────────────────────────────────────────────────────
class ApplyRequest(BaseModel):
    cv_id: int
    cover_letter: str | None = None


class ApplyOut(BaseModel):
    application_id: int
    status: str
    message: str


# ── Application list ──────────────────────────────────────────
class AppTabOut(BaseModel):
    key: str
    label: str
    count: int


class AppAllowedAction(BaseModel):
    key: str
    label: str


class AppJobSummary(BaseModel):
    id: int
    title: str
    company_name: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    is_salary_negotiable: bool = False
    work_type: str | None = None
    status: str | None = None


class ApplicationCardOut(BaseModel):
    id: int
    job: AppJobSummary
    cv_id: int | None = None
    cv_name: str
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    created_at: datetime
    updated_at: datetime
    interview: InterviewInfo | None = None
    allowed_actions: list[AppAllowedAction] = Field(default_factory=list)


class ApplicationListOut(BaseModel):
    items: list[ApplicationCardOut]
    tabs: list[AppTabOut]
    total: int
    page: int
    page_size: int


# ── Application detail ───────────────────────────────────────
class StatusHistoryItem(BaseModel):
    status: str
    status_label: str
    status_tone: str
    note: str | None = None
    changed_at: datetime


class InterviewInfo(BaseModel):
    interview_at: datetime | None = None
    interview_mode: str | None = None
    interview_location: str | None = None


class ApplicationDetailOut(BaseModel):
    id: int
    job: AppJobSummary
    cv_name: str
    cv_id: int | None = None
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    created_at: datetime
    updated_at: datetime
    history: list[StatusHistoryItem] = Field(default_factory=list)
    interview: InterviewInfo | None = None
    allowed_actions: list[AppAllowedAction] = Field(default_factory=list)


# ── Withdraw ──────────────────────────────────────────────────
class WithdrawRequest(BaseModel):
    reason: str | None = None


# ── Cover letter draft ────────────────────────────────────────
class DraftSaveRequest(BaseModel):
    cover_letter: str = Field(max_length=1000)


class DraftOut(BaseModel):
    cover_letter: str
    updated_at: datetime

