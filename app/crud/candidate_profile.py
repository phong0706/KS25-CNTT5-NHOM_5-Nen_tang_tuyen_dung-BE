"""CRUD operations cho hồ sơ ứng viên, kỹ năng, kinh nghiệm và học vấn."""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.candidate import CandidateProfile, CandidateSkill, Education, Experience
from app.schemas.candidate_schema import (
    CandidateProfileCreate,
    CandidateProfileUpdate,
    CandidateSkillCreate,
    CandidateSkillUpdate,
    EducationCreate,
    EducationUpdate,
    ExperienceCreate,
    ExperienceUpdate,
)


# ---------------------------------------------------------------------------
# CandidateProfile CRUD
# ---------------------------------------------------------------------------

def get_profile_by_user_id(db: Session, user_id: int) -> CandidateProfile | None:
    """Lấy hồ sơ của user (kèm relationships: skills, experiences, educations, cvs)."""
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .options(
            joinedload(CandidateProfile.skills),
            joinedload(CandidateProfile.experiences),
            joinedload(CandidateProfile.educations),
            joinedload(CandidateProfile.cvs),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_profile_by_id(db: Session, profile_id: int) -> CandidateProfile | None:
    """Lấy hồ sơ theo ID (kèm relationships)."""
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.id == profile_id)
        .options(
            joinedload(CandidateProfile.skills),
            joinedload(CandidateProfile.experiences),
            joinedload(CandidateProfile.educations),
            joinedload(CandidateProfile.cvs),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def create_profile(db: Session, data: CandidateProfileCreate) -> CandidateProfile:
    """Tạo hồ sơ mới cho user."""
    profile = CandidateProfile(
        user_id=data.user_id,
        date_of_birth=data.date_of_birth,
        address=data.address,
        desired_position=data.desired_position,
        desired_salary=data.desired_salary,
        summary=data.summary,
        is_public=data.is_public,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(
    db: Session, profile: CandidateProfile, data: CandidateProfileUpdate
) -> CandidateProfile:
    """Cập nhật thông tin hồ sơ. Chỉ update các trường được gửi lên."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# CandidateSkill CRUD
# ---------------------------------------------------------------------------

def get_skill_by_id(db: Session, skill_id: int) -> CandidateSkill | None:
    """Lấy kỹ năng theo ID."""
    return db.get(CandidateSkill, skill_id)


def add_skill(db: Session, profile_id: int, data: CandidateSkillCreate) -> CandidateSkill:
    """Thêm kỹ năng cho hồ sơ."""
    skill = CandidateSkill(
        profile_id=profile_id,
        skill_id=data.skill_id,
        skill_name=data.skill_name,
        level=data.level,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def update_skill(
    db: Session, skill: CandidateSkill, data: CandidateSkillUpdate
) -> CandidateSkill:
    """Cập nhật kỹ năng."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)
    
    db.commit()
    db.refresh(skill)
    return skill


def delete_skill(db: Session, skill: CandidateSkill) -> None:
    """Xóa kỹ năng."""
    db.delete(skill)
    db.commit()


# ---------------------------------------------------------------------------
# Experience CRUD
# ---------------------------------------------------------------------------

def get_experience_by_id(db: Session, exp_id: int) -> Experience | None:
    """Lấy kinh nghiệm theo ID."""
    return db.get(Experience, exp_id)


def add_experience(db: Session, profile_id: int, data: ExperienceCreate) -> Experience:
    """Thêm kinh nghiệm làm việc."""
    experience = Experience(
        profile_id=profile_id,
        company_name=data.company_name,
        position=data.position,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
        description=data.description,
    )
    db.add(experience)
    db.commit()
    db.refresh(experience)
    return experience


def update_experience(
    db: Session, experience: Experience, data: ExperienceUpdate
) -> Experience:
    """Cập nhật kinh nghiệm."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(experience, field, value)
    
    db.commit()
    db.refresh(experience)
    return experience


def delete_experience(db: Session, experience: Experience) -> None:
    """Xóa kinh nghiệm."""
    db.delete(experience)
    db.commit()


# ---------------------------------------------------------------------------
# Education CRUD
# ---------------------------------------------------------------------------

def get_education_by_id(db: Session, edu_id: int) -> Education | None:
    """Lấy học vấn theo ID."""
    return db.get(Education, edu_id)


def add_education(db: Session, profile_id: int, data: EducationCreate) -> Education:
    """Thêm học vấn."""
    education = Education(
        profile_id=profile_id,
        school_name=data.school_name,
        major=data.major,
        degree=data.degree,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
        description=data.description,
    )
    db.add(education)
    db.commit()
    db.refresh(education)
    return education


def update_education(
    db: Session, education: Education, data: EducationUpdate
) -> Education:
    """Cập nhật học vấn."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(education, field, value)
    
    db.commit()
    db.refresh(education)
    return education


def delete_education(db: Session, education: Education) -> None:
    """Xóa học vấn."""
    db.delete(education)
    db.commit()
