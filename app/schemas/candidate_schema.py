"""Schema cho ứng viên: hồ sơ, kỹ năng, kinh nghiệm, học vấn và CV.

FastAPI dùng schema để tự kiểm tra dữ liệu: sai kiểu / thiếu trường -> trả lỗi 422.
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# CandidateSkill
# ---------------------------------------------------------------------------
class CandidateSkillBase(BaseModel):
    skill_id: int | None = Field(default=None, examples=[1])
    skill_name: str = Field(min_length=1, max_length=255, examples=["Python"])
    level: str | None = Field(default=None, max_length=50, examples=["Advanced"])


class CandidateSkillCreate(CandidateSkillBase):
    """Dữ liệu FE gửi lên khi thêm kỹ năng cho hồ sơ."""


class CandidateSkillUpdate(BaseModel):
    """Dữ liệu FE gửi lên khi sửa kỹ năng."""
    skill_id: int | None = Field(default=None, examples=[1])
    skill_name: str | None = Field(default=None, min_length=1, max_length=255)
    level: str | None = Field(default=None, max_length=50)


class CandidateSkillOut(CandidateSkillBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
class ExperienceBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=255, examples=["FPT Software"])
    position: str = Field(min_length=1, max_length=255, examples=["Backend Developer"])
    start_date: date = Field(examples=["2023-06-01"])
    end_date: date | None = Field(default=None, examples=["2025-05-01"])
    is_current: bool = Field(default=False, examples=[False])
    description: str | None = Field(default=None, examples=["Phat trien API REST voi FastAPI"])


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    position: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    description: str | None = None


class ExperienceOut(ExperienceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
class EducationBase(BaseModel):
    school_name: str = Field(min_length=1, max_length=255, examples=["DH Cong nghe thong tin"])
    major: str | None = Field(default=None, max_length=255, examples=["Ky thuat phan mem"])
    degree: str | None = Field(default=None, max_length=100, examples=["Bachelor"])
    start_date: date = Field(examples=["2021-09-01"])
    end_date: date | None = Field(default=None, examples=["2025-06-01"])
    is_current: bool = Field(default=False, examples=[False])
    description: str | None = Field(default=None, examples=["GPA 3.6/4.0"])


class EducationCreate(EducationBase):
    pass


class EducationUpdate(BaseModel):
    school_name: str | None = Field(default=None, min_length=1, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    degree: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    description: str | None = None


class EducationOut(EducationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------------------------------------------------------------------------
# Cv
# ---------------------------------------------------------------------------
class CvCreate(BaseModel):
    """Dữ liệu khi tải lên 1 file CV. stored_name do server tự sinh (UUID)."""
    original_name: str = Field(min_length=1, max_length=255, examples=["CV_NguyenVanA.pdf"])
    file_size: int = Field(gt=0, examples=[524288])
    mime_type: str = Field(min_length=1, max_length=127, examples=["application/pdf"])
    is_default: bool = Field(default=False, examples=[False])


class CvOut(BaseModel):
    """Dữ liệu CV trả về cho FE."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_name: str
    stored_name: str
    file_size: int
    mime_type: str
    is_default: bool
    uploaded_at: datetime


# ---------------------------------------------------------------------------
# CandidateProfile
# ---------------------------------------------------------------------------
class CandidateProfileBase(BaseModel):
    date_of_birth: date | None = Field(default=None, examples=["2000-05-15"])
    address: str | None = Field(default=None, max_length=500, examples=["TP. Ho Chi Minh"])
    desired_position: str | None = Field(
        default=None, max_length=255, examples=["Backend Developer"]
    )
    desired_salary: int | None = Field(default=None, ge=0, examples=[20000000])
    summary: str | None = Field(
        default=None, examples=["Sinh vien nam cuoi, dam me backend"]
    )
    is_public: bool = Field(default=True, examples=[True])


class CandidateProfileCreate(CandidateProfileBase):
    """Dữ liệu FE gửi lên khi tạo hồ sơ ứng viên mới."""
    user_id: int = Field(examples=[1])


class CandidateProfileUpdate(BaseModel):
    """Dữ liệu FE gửi lên khi sửa hồ sơ. Trường nào không gửi thì giữ nguyên."""
    date_of_birth: date | None = None
    address: str | None = Field(default=None, max_length=500)
    desired_position: str | None = Field(default=None, max_length=255)
    desired_salary: int | None = Field(default=None, ge=0)
    summary: str | None = None
    is_public: bool | None = None


class CandidateProfileOut(CandidateProfileBase):
    """Dữ liệu hồ sơ trả về cho FE (kèm ID và danh sách liên kết)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    skills: list[CandidateSkillOut] = []
    experiences: list[ExperienceOut] = []
    educations: list[EducationOut] = []
    cvs: list[CvOut] = []
