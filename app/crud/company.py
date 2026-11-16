"""CRUD cho bảng companies."""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.schemas.company_schema import CompanyProfileUpdate
from app.services.notification import NotificationType, create_notification


def create_draft_company(db: Session, *, name: str, employer_id: int) -> Company:
    """Tạo công ty nháp (is_draft=True) khi employer đăng ký."""
    company = Company(
        name=name,
        employer_id=employer_id,
        owner_id=employer_id,
        is_draft=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def get_company_by_employer(db: Session, employer_id: int) -> Company | None:
    """Lấy công ty theo employer_id (mỗi employer chỉ có 1 công ty)."""
    return db.scalar(select(Company).where(Company.employer_id == employer_id))


def update_company(db: Session, company: Company, data: CompanyProfileUpdate) -> Company:
    """Cập nhật thông tin hồ sơ công ty (chỉ các trường được gửi lên)."""
    changes = data.model_dump(exclude_unset=True)
    identity_changed = any(
        field in changes and changes[field] != getattr(company, field)
        for field in ("name", "tax_code")
    )
    for field, value in changes.items():
        setattr(company, field, value)
    if identity_changed:
        if company.status == CompanyStatus.VERIFIED:
            company.status = CompanyStatus.PENDING
            db.execute(
                update(Job)
                .where(
                    Job.company_id == company.id,
                    Job.status.in_(("pending", "published", "PENDING", "OPEN")),
                )
                .values(status="draft", published_at=None)
            )
        if company.verification_submitted_at is not None:
            company.verification_submitted_at = None
        company.verification_rejection_reason = None
        company.verification_document = None
    # Khi employer tự cập nhật hồ sơ, đánh dấu không còn là nháp
    company.is_draft = False
    db.commit()
    db.refresh(company)
    return company


def update_company_logo(db: Session, company: Company, logo_url: str) -> Company:
    """Cập nhật URL logo công ty."""
    company.logo = logo_url
    db.commit()
    db.refresh(company)
    return company


def update_company_cover(db: Session, company: Company, cover_url: str) -> Company:
    """Cập nhật URL ảnh bìa công ty."""
    company.cover_image = cover_url
    db.commit()
    db.refresh(company)
    return company


def submit_company_verification(db: Session, company: Company, tax_code: str) -> Company:
    company.tax_code = tax_code.strip()
    company.status = CompanyStatus.PENDING
    company.verification_rejection_reason = None
    company.verification_submitted_at = datetime.now()
    company.is_draft = False
    db.commit()
    db.refresh(company)
    return company


def get_pending_verifications(db: Session) -> list[Company]:
    return list(
        db.scalars(
            select(Company)
            .where(
                Company.status == CompanyStatus.PENDING,
                Company.verification_submitted_at.is_not(None),
            )
            .order_by(Company.created_at.asc())
        )
    )


def decide_company_verification(
    db: Session,
    company: Company,
    *,
    status: CompanyStatus,
    reason: str | None,
) -> Company:
    company.status = status
    company.verification_rejection_reason = reason if status == CompanyStatus.REJECTED else None
    approved = status == CompanyStatus.VERIFIED
    result = "đã được xác minh" if approved else f"bị từ chối. Lý do: {reason}"
    create_notification(
        db,
        user_id=company.employer_id,
        type=NotificationType.SYSTEM,
        title="Kết quả xác minh công ty",
        message=f"Công ty {company.name} {result}.",
        link="/company/me",
        ref_type="company_verification",
        ref_id=company.id,
        dedupe_key=(
            f"company-verification:{company.id}:"
            f"{company.verification_submitted_at.isoformat()}:{status.value}"
        ),
    )
    db.commit()
    db.refresh(company)
    return company


def get_company_for_review(db: Session, company_id: int) -> Company | None:
    return db.scalar(select(Company).where(Company.id == company_id).with_for_update())
