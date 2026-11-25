"""Model cho quản lý logo công ty (company_logos).
Tuân thủ techrecruit-rules: <= 200 dòng.
"""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CompanyLogo(Base):
    __tablename__ = "company_logos"
    __table_args__ = (
        Index("idx_comp_logos_company", "company_id"),
        Index("idx_comp_logos_status", "status"),
        Index("idx_comp_logos_current", "is_current"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    file_key: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key_2x: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="cho_duyet")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    company = relationship("Company", backref="logos", foreign_keys=[company_id])
