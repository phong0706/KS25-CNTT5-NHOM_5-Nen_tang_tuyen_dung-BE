"""Models cho ứng viên: hồ sơ, kỹ năng, kinh nghiệm, học vấn và CV."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CandidateProfile(Base):
    """Hồ sơ ứng viên — quan hệ 1-1 với bảng users (liên kết qua user_id)."""

    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)

    # Thông tin cá nhân
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Mong muốn nghề nghiệp
    desired_position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desired_salary: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # VNĐ

    # Giới thiệu bản thân (bio)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hiển thị hồ sơ công khai cho nhà tuyển dụng
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    skills: Mapped[list["CandidateSkill"]] = relationship(
        "CandidateSkill", back_populates="profile", cascade="all, delete-orphan"
    )
    experiences: Mapped[list["Experience"]] = relationship(
        "Experience", back_populates="profile", cascade="all, delete-orphan"
    )
    educations: Mapped[list["Education"]] = relationship(
        "Education", back_populates="profile", cascade="all, delete-orphan"
    )
    cvs: Mapped[list["Cv"]] = relationship(
        "Cv", back_populates="profile", cascade="all, delete-orphan"
    )


class CandidateSkill(Base):
    """Kỹ năng của ứng viên (nhiều kỹ năng cho 1 hồ sơ)."""

    __tablename__ = "candidate_skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Tham chiếu đến bảng skills (danh mục) — nullable để cho phép nhập tự do
    skill_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("skills.id", ondelete="SET NULL"), nullable=True
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Ví dụ: Beginner / Intermediate / Advanced

    profile: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="skills")


class Experience(Base):
    """Kinh nghiệm làm việc của ứng viên."""

    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = đang làm
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["CandidateProfile"] = relationship(
        "CandidateProfile", back_populates="experiences"
    )


class Education(Base):
    """Học vấn của ứng viên."""

    __tablename__ = "educations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    major: Mapped[str | None] = mapped_column(String(255), nullable=True)   # Chuyên ngành
    degree: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Bằng cấp
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)      # None = đang học
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["CandidateProfile"] = relationship(
        "CandidateProfile", back_populates="educations"
    )


class Cv(Base):
    """CV (file PDF/DOCX) do ứng viên tải lên."""

    __tablename__ = "cvs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    original_name: Mapped[str] = mapped_column(String(255), nullable=False)   # Tên file gốc
    stored_name: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )  # Tên lưu dưới dạng UUID (không lộ tên thật)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)         # Bytes
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)        # vd: application/pdf
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    profile: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="cvs")
