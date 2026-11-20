"""Models cho cấu hình trang chủ & nhật ký kiểm toán (home_config).
Tuân thủ Bước 1 & techrecruit-rules: < 195 dòng, khóa duy nhất, kiểm soát phiên bản.
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class HomeSalarySettings(Base):
    """Cấu hình hiển thị lương trung vị theo kỹ năng (1 dòng toàn hệ thống)."""
    __tablename__ = "home_salary_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    min_sample: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    max_items: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class HomeSalarySkillOverride(Base):
    """Ghi đè hiển thị kỹ năng (ghim lên đầu hoặc ẩn khỏi danh sách)."""
    __tablename__ = "home_salary_skill_overrides"
    __table_args__ = (
        Index("idx_home_skill_override_skill", "skill_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")  # 'pinned' | 'hidden' | 'auto'
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class HomeFeaturedCompany(Base):
    """Cấu hình ghim doanh nghiệp đang tuyển dụng trên trang chủ."""
    __tablename__ = "home_featured_companies"
    __table_args__ = (
        Index("idx_home_featured_comp_company", "company_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class HomeConfigAudit(Base):
    """Nhật ký kiểm toán thay đổi cấu hình trang chủ."""
    __tablename__ = "home_config_audit"
    __table_args__ = (
        Index("idx_home_audit_section_created", "section", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(50), nullable=False)  # 'salary' | 'companies' | 'all'
    action: Mapped[str] = mapped_column(String(50), nullable=False)   # 'update_settings' | 'update_skills' | 'update_companies'
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
