"""Model Company (thông tin công ty / nhà tuyển dụng).

Trạng thái vòng đời:
PENDING  -> công ty mới tạo, chờ admin xác minh
VERIFIED -> đã được xác minh (hồ sơ hợp lệ)
REJECTED -> bị từ chối (thông tin không hợp lệ)
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.services.public_company_rules import normalize_search_text


class CompanyStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("idx_companies_visible_name", "is_visible", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Khóa ngoại liên kết tới bảng users (tự xóa khi user bị xóa)
    employer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ID người sở hữu (hỗ trợ truy vấn nhanh theo owner)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Tên công ty, tagline & slug URL ASCII duy nhất
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(120), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)

    # URL logo (giữ cả logo & logo_url để tương thích cả 2 nhánh, thêm logo_url_2x cho srcset)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_url_2x: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # URL ảnh bìa (giữ cả cover_image & cover_url để tương thích cả 2 nhánh)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Mã số thuế
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Ảnh giấy phép kinh doanh dùng cho bước xác minh
    verification_document: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Quy mô công ty (size_range chuẩn hóa + giữ tương thích cột cũ)
    size_range: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Ngành nghề & địa điểm chính
    industry_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Địa chỉ & văn bản tìm kiếm chuẩn hóa (tự cập nhật khi lưu)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    search_text: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)

    # Website
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Mô tả công ty
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Trạng thái hiển thị công khai & xác minh của Admin
    status: Mapped[CompanyStatus] = mapped_column(
        SQLEnum(CompanyStatus), default=CompanyStatus.PENDING, nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), default="chua_xac_minh", nullable=False, index=True
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Cờ đánh dấu công ty nháp lúc đăng ký
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)

    # Quản lý trạng thái & lịch sử tải lên logo (active | removed | missing)
    logo_status: Mapped[str] = mapped_column(String(20), default="missing", nullable=False)
    logo_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    logo_uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logo_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Thời gian tạo / cập nhật
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


def _sync_company_computed_fields(_mapper, _connection, target: Company) -> None:
    target.search_text = normalize_search_text(target.name, target.tagline, target.address)[:500]
    if target.verification_status == "da_xac_minh" or target.status == CompanyStatus.VERIFIED:
        target.is_verified = True
    if not target.slug and target.name:
        import uuid
        from app.services.public_company_rules import slugify_company
        target.slug = f"{slugify_company(target.name)}-{uuid.uuid4().hex[:6]}"[:120]


event.listen(Company, "before_insert", _sync_company_computed_fields)
event.listen(Company, "before_update", _sync_company_computed_fields)