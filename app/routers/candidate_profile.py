"""Router quản lý hồ sơ ứng viên (/api/candidate/profile và /api/profiles)."""
import datetime
import io
import json
import os
import uuid

from PIL import Image
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import is_owner_or_admin, require_owner
from app.core.security import get_current_user, get_optional_user, role_required
from app.crud import candidate_profile as profile_crud
from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.models.candidate_profile import (
    CandidateEducation,
    CandidateExperience,
)
from app.models.user import User
from app.schemas.candidate_profile import (
    CandidateProfileOut,
    CandidateProfilePatch,
    CompletionMissingItem,
    EducationIn,
    ExperienceIn,
    ProfileCompletionOut,
    SkillsUpdateIn,
)
from app.schemas.candidate_schema import (
    CandidateProfileCreate,
    CandidateProfileOut as CandidateProfileDetailOut,
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

# Không gắn prefix cố định ở router để phục vụ đồng thời cả /candidate/... và /profiles/...
router = APIRouter(tags=["Candidate Profile"])


# ===========================================================================
# PHẦN 1: API HỒ SƠ ỨNG VIÊN (/api/candidate/profile - nhánh feat/T3D36B4)
# ===========================================================================


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


@router.get("/candidate/profile", response_model=CandidateProfileOut)
def get_candidate_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    return _build_profile_out(db, current_user)


@router.patch("/candidate/profile", response_model=CandidateProfileOut)
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


@router.put("/candidate/profile/skills", response_model=CandidateProfileOut)
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


def _validate_experience_dates(start_month: str, end_month: str | None, is_current: bool):
    try:
        s_y, s_m = map(int, start_month.split("-"))
    except Exception:
        raise HTTPException(status_code=422, detail="Định dạng tháng bắt đầu không hợp lệ (YYYY-MM)")

    now = datetime.date.today()
    if s_y > now.year or (s_y == now.year and s_m > now.month):
        raise HTTPException(status_code=422, detail="Thời gian bắt đầu không được ở tương lai")

    if not is_current:
        if not end_month:
            raise HTTPException(status_code=422, detail="Vui lòng chọn tháng kết thúc hoặc đánh dấu 'Tôi đang làm việc tại đây'")
        try:
            e_y, e_m = map(int, end_month.split("-"))
        except Exception:
            raise HTTPException(status_code=422, detail="Định dạng tháng kết thúc không hợp lệ (YYYY-MM)")
        if e_y < s_y or (e_y == s_y and e_m < s_m):
            raise HTTPException(status_code=422, detail="Thời gian kết thúc không được trước thời gian bắt đầu")


def _validate_education_dates(start_year: int, end_year: int | None):
    now_year = datetime.date.today().year
    if start_year > now_year + 5:
        raise HTTPException(status_code=422, detail="Năm bắt đầu không hợp lệ")
    if end_year is not None and end_year < start_year:
        raise HTTPException(status_code=422, detail="Năm kết thúc không được trước năm bắt đầu")


@router.post("/candidate/profile/experiences", response_model=CandidateProfileOut)
def create_candidate_experience(
    payload: ExperienceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Thêm một mục kinh nghiệm làm việc."""
    _validate_experience_dates(payload.start_month, payload.end_month, payload.is_current)

    exp = CandidateExperience(
        user_id=current_user.id,
        title=payload.title.strip(),
        company=payload.company.strip(),
        start_month=payload.start_month,
        end_month=None if payload.is_current else payload.end_month,
        is_current=payload.is_current,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(exp)

    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1
    db.add(profile)
    db.commit()

    return _build_profile_out(db, current_user)


@router.put("/candidate/profile/experiences/{exp_id}", response_model=CandidateProfileOut)
def update_candidate_experience(
    exp_id: int,
    payload: ExperienceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Cập nhật một mục kinh nghiệm làm việc (kiểm tra quyền sở hữu)."""
    exp = db.get(CandidateExperience, exp_id)
    if not exp or exp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục kinh nghiệm này.")

    _validate_experience_dates(payload.start_month, payload.end_month, payload.is_current)

    exp.title = payload.title.strip()
    exp.company = payload.company.strip()
    exp.start_month = payload.start_month
    exp.end_month = None if payload.is_current else payload.end_month
    exp.is_current = payload.is_current
    exp.description = payload.description.strip() if payload.description else None

    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1
    db.add(profile)
    db.commit()

    return _build_profile_out(db, current_user)


@router.delete("/candidate/profile/experiences/{exp_id}", response_model=CandidateProfileOut)
def delete_candidate_experience(
    exp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Xóa một mục kinh nghiệm làm việc (kiểm tra quyền sở hữu)."""
    exp = db.get(CandidateExperience, exp_id)
    if not exp or exp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục kinh nghiệm này.")

    db.delete(exp)
    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1
    db.add(profile)
    db.commit()

    return _build_profile_out(db, current_user)


@router.post("/candidate/profile/educations", response_model=CandidateProfileOut)
def create_candidate_education(
    payload: EducationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Thêm một mục học vấn."""
    _validate_education_dates(payload.start_year, payload.end_year)

    edu = CandidateEducation(
        user_id=current_user.id,
        school=payload.school.strip(),
        major=payload.major.strip(),
        degree=payload.degree.strip(),
        start_year=payload.start_year,
        end_year=payload.end_year,
    )
    db.add(edu)

    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1
    db.add(profile)
    db.commit()

    return _build_profile_out(db, current_user)


@router.put("/candidate/profile/educations/{edu_id}", response_model=CandidateProfileOut)
def update_candidate_education(
    edu_id: int,
    payload: EducationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Cập nhật một mục học vấn (kiểm tra quyền sở hữu)."""
    edu = db.get(CandidateEducation, edu_id)
    if not edu or edu.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục học vấn này.")

    _validate_education_dates(payload.start_year, payload.end_year)

    edu.school = payload.school.strip()
    edu.major = payload.major.strip()
    edu.degree = payload.degree.strip()
    edu.start_year = payload.start_year
    edu.end_year = payload.end_year

    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1
    db.add(profile)
    db.commit()

    return _build_profile_out(db, current_user)


@router.delete("/candidate/profile/educations/{edu_id}", response_model=CandidateProfileOut)
def delete_candidate_education(
    edu_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Xóa một mục học vấn (kiểm tra quyền sở hữu)."""
    edu = db.get(CandidateEducation, edu_id)
    if not edu or edu.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục học vấn này.")

    db.delete(edu)
    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1
    db.add(profile)
    db.commit()

    return _build_profile_out(db, current_user)


AVATAR_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "avatars"
)


def _validate_image_magic_bytes(header: bytes) -> str:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "webp"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Định dạng file không hợp lệ. Chỉ chấp nhận file ảnh PNG, JPEG, WebP hợp lệ.",
    )


@router.post("/candidate/profile/avatar", response_model=CandidateProfileOut)
async def upload_candidate_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Tải lên ảnh đại diện: kiểm tra magic bytes, bóc EXIF bằng Pillow, xuất WebP 0.85."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dung lượng ảnh vượt quá giới hạn 5MB.",
        )

    # Kiểm tra magic byte
    _validate_image_magic_bytes(content[:16])

    # Kiểm tra file ảnh hợp lệ qua Pillow
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh bị hỏng hoặc không đúng định dạng.",
        )

    # Mở lại để xử lý và bóc EXIF
    img = Image.open(io.BytesIO(content))
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        converted = img.convert("RGBA")
    else:
        converted = img.convert("RGB")

    # Resize về 512x512
    converted.thumbnail((512, 512), Image.Resampling.LANCZOS)

    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.webp"
    file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)

    # Lưu WebP chất lượng 85, không EXIF
    converted.save(file_path, "WEBP", quality=85)

    current_user.avatar_url = f"http://127.0.0.1:8000/uploads/avatars/{filename}"
    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1

    db.add(current_user)
    db.add(profile)
    db.commit()
    db.refresh(current_user)
    db.refresh(profile)

    return _build_profile_out(db, current_user)


@router.delete("/candidate/profile/avatar", response_model=CandidateProfileOut)
def delete_candidate_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    """Xóa ảnh đại diện hiện tại của ứng viên."""
    current_user.avatar_url = None
    profile = _get_or_create_profile(db, current_user.id)
    profile.version = getattr(profile, "version", 1) + 1

    db.add(current_user)
    db.add(profile)
    db.commit()
    db.refresh(current_user)
    db.refresh(profile)

    return _build_profile_out(db, current_user)


# ===========================================================================
# PHẦN 2: API QUẢN LÝ HỒ SƠ CHI TIẾT (/api/profiles - nhánh develop)
# ===========================================================================


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


@router.get("/profiles/me", response_model=CandidateProfileDetailOut, summary="Xem hồ sơ của mình")
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


@router.get("/profiles/{profile_id}", response_model=CandidateProfileDetailOut, summary="Xem hồ sơ")
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
    "/profiles",
    response_model=CandidateProfileDetailOut,
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
    "/profiles/{profile_id}", response_model=CandidateProfileDetailOut, summary="Cập nhật hồ sơ"
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


@router.post(
    "/profiles/{profile_id}/skills",
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
    "/profiles/{profile_id}/skills/{skill_id}",
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
    "/profiles/{profile_id}/skills/{skill_id}",
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


@router.post(
    "/profiles/{profile_id}/experiences",
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
    "/profiles/{profile_id}/experiences/{exp_id}",
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
    "/profiles/{profile_id}/experiences/{exp_id}",
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


@router.post(
    "/profiles/{profile_id}/educations",
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
    "/profiles/{profile_id}/educations/{edu_id}",
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
    "/profiles/{profile_id}/educations/{edu_id}",
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