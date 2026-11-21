"""Schemas Pydantic cho quản lý hồ sơ ứng tuyển & lịch phỏng vấn (NTD & Admin).
Giới hạn: < 200 dòng.
"""
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.application import AppTabOut, InterviewInfo, StatusHistoryItem


class ApplicantCandidateOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None = None
    avatar_url: str | None = None
    public_id: str | None = None


class ApplicantJobOut(BaseModel):
    id: int
    title: str
    company_slug: str | None = None
    company_name: str | None = None


class EmployerApplicationItemOut(BaseModel):
    id: int
    job: ApplicantJobOut
    candidate: ApplicantCandidateOut
    cv_id: int | None = None
    cv_name: str | None = None
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    is_viewed: bool = False
    match_score: int = 70
    created_at: datetime
    updated_at: datetime
    interview: InterviewInfo | None = None


class EmployerApplicationListOut(BaseModel):
    items: list[EmployerApplicationItemOut]
    tabs: list[AppTabOut]
    jobs: list[ApplicantJobOut]
    total: int
    page: int
    page_size: int


class EmployerApplicationDetailOut(BaseModel):
    id: int
    job: ApplicantJobOut
    candidate: ApplicantCandidateOut
    cv_id: int | None = None
    cv_name: str | None = None
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    is_viewed: bool = False
    match_score: int = 70
    created_at: datetime
    updated_at: datetime
    interview: InterviewInfo | None = None
    history: list[StatusHistoryItem] = Field(default_factory=list)
    allowed_transitions: list[str] = Field(default_factory=list)


class ApplicationNoteOut(BaseModel):
    id: int
    application_id: int
    author_id: int
    author_name: str
    content: str
    created_at: datetime


class ApplicationNoteCreateIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class EmployerInterviewScheduleIn(BaseModel):
    scheduled_at: datetime
    duration_min: int = Field(default=45, ge=15, le=180)
    mode: str = "Trực tuyến qua Google Meet"
    location_or_link: str | None = None
    interviewer: str | None = None
    note: str | None = None
    force: bool = False


class InterviewCancelIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class InterviewItemOut(BaseModel):
    id: int
    application_id: int
    candidate_name: str
    candidate_avatar: str | None = None
    candidate_email: str | None = None
    job_id: int
    job_title: str
    scheduled_at: datetime
    duration_min: int
    mode: str
    location_or_link: str | None = None
    interviewer: str | None = None
    note: str | None = None
    status: str
    cancel_reason: str | None = None


class EmployerStatusUpdateIn(BaseModel):
    status: str = Field(max_length=32)
    note: str | None = Field(default=None, max_length=500)
    rejection_reason_slug: str | None = None



# ── ADMIN SCHEMAS ─────────────────────────────────────────────

class AdminAppEmployerOut(BaseModel):
    id: int
    full_name: str
    email: str
    company_name: str | None = None


class AdminApplicationItemOut(BaseModel):
    id: int
    job: ApplicantJobOut
    candidate: ApplicantCandidateOut
    employer: AdminAppEmployerOut
    cv_id: int | None = None
    cv_name: str
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    created_at: datetime
    interview: InterviewInfo | None = None
    history_count: int = 0


class AdminApplicationListOut(BaseModel):
    items: list[AdminApplicationItemOut]
    tabs: list[AppTabOut]
    total: int
    page: int
    page_size: int


class AdminApplicationDetailOut(BaseModel):
    id: int
    job: ApplicantJobOut
    candidate: ApplicantCandidateOut
    employer: AdminAppEmployerOut
    cv_id: int | None = None
    cv_name: str
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    is_viewed: bool = False
    match_score: int = 70
    created_at: datetime
    updated_at: datetime
    interview: InterviewInfo | None = None
    history: list[StatusHistoryItem] = Field(default_factory=list)
