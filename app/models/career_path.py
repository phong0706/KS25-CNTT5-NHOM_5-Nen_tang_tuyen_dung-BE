"""Models lưu trọng số kỹ năng theo vai trò, thống kê mẫu và cấu hình chuyển họ nghề."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint
from app.db.session import Base


class CareerRoleTransition(Base):
    """Bảng cấu hình đường đi chuyển họ vai trò do Admin quản lý."""
    __tablename__ = "career_role_transitions"
    __table_args__ = (
        UniqueConstraint("from_family_slug", "to_family_slug", name="uq_career_transition_pair"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_family_slug = Column(String(64), nullable=False, index=True)
    to_family_slug = Column(String(64), nullable=False, index=True)
    min_level_order = Column(Integer, nullable=False, default=3)
    is_active = Column(Boolean, nullable=False, default=True)
    note = Column(String(255), nullable=True)


class CareerRoleStat(Base):
    """Bảng lưu thống kê mẫu và lương trung vị đã tính sẵn của từng vai trò (family + level)."""
    __tablename__ = "career_role_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_slug = Column(String(128), nullable=False, unique=True, index=True)
    role_name = Column(String(160), nullable=False)
    family_slug = Column(String(64), nullable=False, index=True)
    family_name = Column(String(120), nullable=False)
    level_slug = Column(String(64), nullable=False, index=True)
    level_name = Column(String(80), nullable=False)
    level_order = Column(Integer, nullable=False, index=True)
    sample_size = Column(Integer, nullable=False, default=0)
    salary_sample_size = Column(Integer, nullable=False, default=0)
    salary_median = Column(Integer, nullable=True)
    is_sufficient = Column(Boolean, nullable=False, default=False)
    data_as_of = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class CareerRoleSkillWeight(Base):
    """Bảng lưu trọng số w(vai trò, kỹ năng) = job_count / total_role_jobs."""
    __tablename__ = "career_role_skill_weights"
    __table_args__ = (
        UniqueConstraint("role_slug", "skill_name", name="uq_career_role_skill"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_slug = Column(String(128), nullable=False, index=True)
    skill_name = Column(String(100), nullable=False)
    job_count = Column(Integer, nullable=False, default=0)
    total_role_jobs = Column(Integer, nullable=False, default=0)
    weight = Column(Float, nullable=False, default=0.0)
    data_as_of = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
