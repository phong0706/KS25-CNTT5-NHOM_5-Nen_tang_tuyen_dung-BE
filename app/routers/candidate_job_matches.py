"""Router cho chức năng Việc làm phù hợp (Candidate Job Matches).
Tuân thủ techrecruit-rules: <= 200 dòng, role-protected candidate.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.user import User
from app.services.job_matching_service import (
    get_candidate_matches_page,
    get_or_create_candidate_settings,
)

router = APIRouter(prefix="/candidate/job-matches", tags=["Candidate Job Matches"])


class CandidateMatchingSettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    open_to_relocate: Optional[bool] = None


class CompanySummary(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    logo_url: Optional[str] = None


class JobMatchItem(BaseModel):
    job_id: int
    title: str
    company: CompanySummary
    location: Optional[str] = None
    level: Optional[str] = None
    salary_display: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    is_salary_negotiable: bool = False
    total_score: float
    match_percentage: int
    skill_score: float
    level_score: float
    place_score: float
    salary_score: float
    matched_skills: List[str] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    published_at: Optional[str] = None
    formula_version: str


class JobMatchesResponse(BaseModel):
    status: str
    items: List[JobMatchItem]
    total: int
    page: int
    size: int
    formula_version: str
    data_as_of: str


@router.get("", response_model=JobMatchesResponse, summary="Lấy danh sách việc làm phù hợp cho ứng viên")
def get_job_matches(
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    size: int = Query(10, ge=1, le=50, description="Số lượng mục mỗi trang (1-50)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    result = get_candidate_matches_page(db, current_user.id, page=page, size=size)
    return result


@router.get("/settings", summary="Lấy cài đặt gợi ý việc làm")
def get_matching_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    setting = get_or_create_candidate_settings(db, current_user.id)
    return {
        "is_enabled": setting.is_enabled,
        "open_to_relocate": setting.open_to_relocate,
    }


@router.put("/settings", summary="Cập nhật cài đặt gợi ý việc làm")
def update_matching_settings(
    payload: CandidateMatchingSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    setting = get_or_create_candidate_settings(db, current_user.id)
    if payload.is_enabled is not None:
        setting.is_enabled = payload.is_enabled
    if payload.open_to_relocate is not None:
        setting.open_to_relocate = payload.open_to_relocate

    db.commit()
    db.refresh(setting)
    return {
        "is_enabled": setting.is_enabled,
        "open_to_relocate": setting.open_to_relocate,
    }
