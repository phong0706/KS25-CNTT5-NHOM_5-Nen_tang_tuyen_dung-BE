"""Model CompanyVerification cho bảng company_verifications."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class CompanyVerification(Base):
    __tablename__ = "company_verifications"
    __table_args__ = (
        Index("idx_cv_company_created", "company_id", "submitted_at"),
        Index("idx_cv_status_submitted", "status", "submitted_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    mst: Mapped[str] = mapped_column(String(20), nullable=False)
    mst_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="cho_duyet")

    license_storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    license_original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    license_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
