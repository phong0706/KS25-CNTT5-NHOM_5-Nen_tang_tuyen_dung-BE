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


class ApplicantJobOut(BaseModel):
    id: int
    title: str


class EmployerApplicationItemOut(BaseModel):
    id: int
    job: ApplicantJobOut
    candidate: ApplicantCandidateOut
    cv_id: int | None = None
    cv_name: str
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
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
    cv_name: str
    cover_letter: str | None = None
    status: str
    status_label: str
    status_tone: str
    created_at: datetime
    updated_at: datetime
    interview: InterviewInfo | None = None
    history: list[StatusHistoryItem] = Field(default_factory=list)


class EmployerStatusUpdateIn(BaseModel):
    status: str
    note: str | None = None


class EmployerInterviewScheduleIn(BaseModel):
    interview_at: datetime
    interview_mode: str = "Trực tuyến qua Google Meet"
    interview_location: str | None = None
    note: str | None = None


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
    created_at: datetime
    updated_at: datetime
    interview: InterviewInfo | None = None
    history: list[StatusHistoryItem] = Field(default_factory=list)
