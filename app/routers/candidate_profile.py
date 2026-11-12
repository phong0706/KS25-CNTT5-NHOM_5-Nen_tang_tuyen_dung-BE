"""API quản lý hồ sơ ứng viên (CandidateProfile).

Endpoints:
    GET    /api/profiles/me                              - Xem hồ sơ của mình
    GET    /api/profiles/{profile_id}                    - Xem hồ sơ (public hoặc của mình)
    POST   /api/profiles                                 - Tạo hồ sơ mới
    PUT    /api/profiles/{profile_id}                    - Cập nhật hồ sơ

    POST   /api/profiles/{profile_id}/skills             - Thêm kỹ năng
    PUT    /api/profiles/{profile_id}/skills/{skill_id}  - Sửa kỹ năng
    DELETE /api/profiles/{profile_id}/skills/{skill_id}  - Xóa kỹ năng

    POST   /api/profiles/{profile_id}/experiences        - Thêm kinh nghiệm
    PUT    /api/profiles/{profile_id}/experiences/{exp_id} - Sửa kinh nghiệm
    DELETE /api/profiles/{profile_id}/experiences/{exp_id} - Xóa kinh nghiệm

    POST   /api/profiles/{profile_id}/educations         - Thêm học vấn
    PUT    /api/profiles/{profile_id}/educations/{edu_id} - Sửa học vấn
    DELETE /api/profiles/{profile_id}/educations/{edu_id} - Xóa học vấn
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import is_owner_or_admin, require_owner
from app.core.security import get_current_user, get_optional_user
from app.crud import candidate_profile as profile_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.candidate_schema import (
    CandidateProfileCreate,
    CandidateProfileOut,
    CandidateProfileUpdate,
    CandidateSkillCreate,
    CandidateSkillOut,
    CandidateSkillUpdate,
    EducationCreate,
    EducationOut,
    EducationUpdate,
    ExperienceCreate,
    ExperienceOut,
    ExperienceUpdate,
)

router = APIRouter(prefix="/profiles", tags=["Candidate Profile"])


# ---------------------------------------------------------------------------
# Helper: Check ownership
# ---------------------------------------------------------------------------


def _check_profile_ownership(profile_id: int, current_user: User, db: Session):
    """Kiểm tra quyền sở hữu hồ sơ. Raise 404/403 nếu không hợp lệ."""
    profile = profile_crud.get_profile_by_id(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ",
        )

    require_owner(profile.user_id, current_user)
    return profile


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------


@router.get("/me", response_model=CandidateProfileOut, summary="Xem hồ sơ của mình")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lấy hồ sơ của user đang đăng nhập (kèm skills, experiences, educations, cvs)."""
    profile = profile_crud.get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bạn chưa có hồ sơ. Hãy tạo hồ sơ trước.",
        )
    return profile


@router.get("/{profile_id}", response_model=CandidateProfileOut, summary="Xem hồ sơ")
def get_profile(
    profile_id: int,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Xem hồ sơ ứng viên.

    - Hồ sơ công khai (is_public=True) → mọi người (kể cả khách) xem được
    - Hồ sơ riêng tư (is_public=False) → chỉ chủ hồ sơ hoặc admin xem được, người khác trả 403
    """
    profile = profile_crud.get_profile_by_id(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ",
        )

    if not profile.is_public:
        if current_user is None or not is_owner_or_admin(profile.user_id, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hồ sơ này ở chế độ riêng tư",
            )

    return profile


@router.post(
    "",
    response_model=CandidateProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo hồ sơ mới",
)
def create_profile(
    data: CandidateProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tạo hồ sơ ứng viên mới.

    - Mỗi user chỉ có 1 hồ sơ duy nhất
    - data.user_id phải khớp với current_user.id
    """
    if data.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn chỉ có thể tạo hồ sơ cho chính mình",
        )

    existing = profile_crud.get_profile_by_user_id(db, data.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã có hồ sơ rồi. Dùng PUT /profiles/{id} để cập nhật.",
        )

    profile = profile_crud.create_profile(db, data)
    return profile


@router.put(
    "/{profile_id}", response_model=CandidateProfileOut, summary="Cập nhật hồ sơ"
)
def update_profile(
    profile_id: int,
    data: CandidateProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin hồ sơ. Chỉ chủ hồ sơ hoặc admin mới được phép sửa."""
    profile = _check_profile_ownership(profile_id, current_user, db)
    updated = profile_crud.update_profile(db, profile, data)
    return updated


# ---------------------------------------------------------------------------
# Skill endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{profile_id}/skills",
    response_model=CandidateSkillOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm kỹ năng",
)
def add_skill(
    profile_id: int,
    data: CandidateSkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thêm kỹ năng cho hồ sơ. Chỉ chủ hồ sơ mới được phép thêm."""
    _check_profile_ownership(profile_id, current_user, db)
    skill = profile_crud.add_skill(db, profile_id, data)
    return skill


@router.put(
    "/{profile_id}/skills/{skill_id}",
    response_model=CandidateSkillOut,
    summary="Sửa kỹ năng",
)
def update_skill(
    profile_id: int,
    skill_id: int,
    data: CandidateSkillUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cập nhật kỹ năng. Chỉ chủ hồ sơ mới được phép sửa."""
    _check_profile_ownership(profile_id, current_user, db)

    skill = profile_crud.get_skill_by_id(db, skill_id)
    if not skill or skill.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kỹ năng",
        )

    updated = profile_crud.update_skill(db, skill, data)
    return updated


@router.delete(
    "/{profile_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa kỹ năng",
)
def delete_skill(
    profile_id: int,
    skill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xóa kỹ năng. Chỉ chủ hồ sơ mới được phép xóa."""
    _check_profile_ownership(profile_id, current_user, db)

    skill = profile_crud.get_skill_by_id(db, skill_id)
    if not skill or skill.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kỹ năng",
        )

    profile_crud.delete_skill(db, skill)
    return None


# ---------------------------------------------------------------------------
# Experience endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{profile_id}/experiences",
    response_model=ExperienceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm kinh nghiệm",
)
def add_experience(
    profile_id: int,
    data: ExperienceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thêm kinh nghiệm làm việc. Chỉ chủ hồ sơ mới được phép thêm."""
    _check_profile_ownership(profile_id, current_user, db)
    experience = profile_crud.add_experience(db, profile_id, data)
    return experience


@router.put(
    "/{profile_id}/experiences/{exp_id}",
    response_model=ExperienceOut,
    summary="Sửa kinh nghiệm",
)
def update_experience(
    profile_id: int,
    exp_id: int,
    data: ExperienceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cập nhật kinh nghiệm. Chỉ chủ hồ sơ mới được phép sửa."""
    _check_profile_ownership(profile_id, current_user, db)

    experience = profile_crud.get_experience_by_id(db, exp_id)
    if not experience or experience.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kinh nghiệm",
        )

    updated = profile_crud.update_experience(db, experience, data)
    return updated


@router.delete(
    "/{profile_id}/experiences/{exp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa kinh nghiệm",
)
def delete_experience(
    profile_id: int,
    exp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xóa kinh nghiệm. Chỉ chủ hồ sơ mới được phép xóa."""
    _check_profile_ownership(profile_id, current_user, db)

    experience = profile_crud.get_experience_by_id(db, exp_id)
    if not experience or experience.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kinh nghiệm",
        )

    profile_crud.delete_experience(db, experience)
    return None


# ---------------------------------------------------------------------------
# Education endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{profile_id}/educations",
    response_model=EducationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm học vấn",
)
def add_education(
    profile_id: int,
    data: EducationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thêm học vấn. Chỉ chủ hồ sơ mới được phép thêm."""
    _check_profile_ownership(profile_id, current_user, db)
    education = profile_crud.add_education(db, profile_id, data)
    return education


@router.put(
    "/{profile_id}/educations/{edu_id}",
    response_model=EducationOut,
    summary="Sửa học vấn",
)
def update_education(
    profile_id: int,
    edu_id: int,
    data: EducationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cập nhật học vấn. Chỉ chủ hồ sơ mới được phép sửa."""
    _check_profile_ownership(profile_id, current_user, db)

    education = profile_crud.get_education_by_id(db, edu_id)
    if not education or education.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học vấn",
        )

    updated = profile_crud.update_education(db, education, data)
    return updated


@router.delete(
    "/{profile_id}/educations/{edu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa học vấn",
)
def delete_education(
    profile_id: int,
    edu_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xóa học vấn. Chỉ chủ hồ sơ mới được phép xóa."""
    _check_profile_ownership(profile_id, current_user, db)

    education = profile_crud.get_education_by_id(db, edu_id)
    if not education or education.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học vấn",
        )

    profile_crud.delete_education(db, education)
    return None
