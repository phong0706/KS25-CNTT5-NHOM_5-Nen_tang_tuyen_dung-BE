"""Router hồ sơ ứng viên (/api/candidate/profile)."""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.candidate_profile import (
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
)
from app.models.user import User
from app.schemas.candidate_profile import (
    CandidateProfileOut,
    CandidateProfilePatch,
    CompletionMissingItem,
    ProfileCompletionOut,
    SkillsUpdateIn,
)

router = APIRouter(prefix="/candidate", tags=["Candidate Profile"])


def _parse_skills(skills_json: str | None) -> list[str]:
    if not skills_json:
        return []
    try:
        data = json.loads(skills_json)
        return [str(s) for s in data] if isinstance(data, list) else []
    except Exception:
        return []


def _compute_completion(
    user: User,
    profile: CandidateProfile,
    skills: list[str],
    experiences: list[CandidateExperience],
    educations: list[CandidateEducation],
) -> ProfileCompletionOut:
    checks = [
        (
            "experiences",
            "Thêm kinh nghiệm làm việc",
            25,
            "section-experiences",
            len(experiences) > 0,
        ),
        (
            "basic",
            "Hoàn thiện thông tin cá nhân",
            20,
            "section-basic-info",
            bool(user.full_name and user.phone and profile.headline and profile.location),
        ),
        ("skills", "Thêm kỹ năng", 20, "section-skills", len(skills) > 0),
        (
            "educations",
            "Thêm học vấn",
            15,
            "section-educations",
            len(educations) > 0,
        ),
        ("avatar", "Tải ảnh đại diện", 10, "avatar-upload-trigger", bool(user.avatar_url)),
        (
            "bio",
            "Viết giới thiệu bản thân",
            10,
            "section-bio",
            bool(profile.bio and len(profile.bio.strip()) >= 20),
        ),
    ]

    percent = sum(weight for _, _, weight, _, done in checks if done)
    missing = [
        CompletionMissingItem(
            key=key, label=label, weight=weight, target_section=target
        )
        for key, label, weight, target, done in checks
        if not done
    ]
    missing.sort(key=lambda item: item.weight, reverse=True)
    return ProfileCompletionOut(percent=percent, missing=missing[:3])


def _get_or_create_profile(db: Session, user_id: int) -> CandidateProfile:
    profile = db.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    if not profile:
        profile = CandidateProfile(user_id=user_id, is_searchable=True)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _build_profile_out(db: Session, user: User) -> CandidateProfileOut:
    profile = _get_or_create_profile(db, user.id)
    skills = _parse_skills(profile.skills_json)
    experiences = list(
        db.scalars(
            select(CandidateExperience)
            .where(CandidateExperience.user_id == user.id)
            .order_by(CandidateExperience.start_month.desc(), CandidateExperience.id.desc())
        ).all()
    )
    educations = list(
        db.scalars(
            select(CandidateEducation)
            .where(CandidateEducation.user_id == user.id)
            .order_by(CandidateEducation.start_year.desc(), CandidateEducation.id.desc())
        ).all()
    )
    completion = _compute_completion(user, profile, skills, experiences, educations)

    return CandidateProfileOut(
        id=profile.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        avatar_url=user.avatar_url,
        headline=profile.headline,
        birth_date=profile.birth_date,
        location=profile.location,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        bio=profile.bio,
        skills=skills,
        is_searchable=profile.is_searchable,
        version=getattr(profile, "version", 1),
        experiences=experiences,
        educations=educations,
        completion=completion,
    )


@router.get("/profile", response_model=CandidateProfileOut)
def get_candidate_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    return _build_profile_out(db, current_user)


@router.patch("/profile", response_model=CandidateProfileOut)
def patch_candidate_profile(
    payload: CandidateProfilePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    profile = _get_or_create_profile(db, current_user.id)
    data = payload.model_dump(exclude_unset=True)

    # Kiểm tra version chống xung đột chỉnh sửa đồng thời (409 Conflict)
    req_version = data.pop("version", None)
    current_version = getattr(profile, "version", 1)
    if req_version is not None and req_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hồ sơ đã được cập nhật ở một phiên khác. Vui lòng tải lại trang để xem dữ liệu mới nhất.",
        )

    if "full_name" in data and data["full_name"] is not None:
        name = data.pop("full_name").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Họ tên không được để trống")
        current_user.full_name = name

    if "phone" in data:
        current_user.phone = data.pop("phone")

    # Chỉ cập nhật các trường được phép của candidate_profiles (bỏ qua trường lạ)
    allowed_fields = {
        "headline", "birth_date", "location", "linkedin_url",
        "github_url", "portfolio_url", "bio", "is_searchable"
    }
    for field, value in data.items():
        if field in allowed_fields:
            setattr(profile, field, value)

    # Tăng version
    profile.version = current_version + 1

    db.add(current_user)
    db.add(profile)
    db.commit()
    db.refresh(current_user)
    db.refresh(profile)
    return _build_profile_out(db, current_user)


@router.put("/profile/skills", response_model=CandidateProfileOut)
def update_candidate_skills(
    payload: SkillsUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Cập nhật toàn bộ danh sách kỹ năng của ứng viên."""
    profile = _get_or_create_profile(db, current_user.id)

    # Kiểm tra version chống xung đột chỉnh sửa đồng thời (409 Conflict)
    current_version = getattr(profile, "version", 1)
    if payload.version is not None and payload.version != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hồ sơ đã được cập nhật ở một phiên khác. Vui lòng tải lại trang để xem dữ liệu mới nhất.",
        )

    # Chuẩn hóa kỹ năng: trim, không rỗng, không trùng không phân biệt hoa thường, tối đa 30
    seen = set()
    cleaned_skills = []
    for s in payload.skills:
        clean_s = str(s).strip()
        if clean_s and clean_s.lower() not in seen:
            seen.add(clean_s.lower())
            cleaned_skills.append(clean_s)
        if len(cleaned_skills) >= 30:
            break

    profile.skills_json = json.dumps(cleaned_skills, ensure_ascii=False)
    profile.version = getattr(profile, "version", 1) + 1

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _build_profile_out(db, current_user)


