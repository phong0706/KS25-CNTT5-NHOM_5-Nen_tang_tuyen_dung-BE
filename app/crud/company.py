"""CRUD cho bảng companies."""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.user import User
from app.schemas.company_schema import CompanyProfileUpdate
from app.services.notification import NotificationType, create_notification
from app.services.public_company_rules import generate_unique_company_slug


def create_draft_company(db: Session, *, name: str, employer_id: int) -> Company:
    """Tạo công ty nháp (is_draft=True) khi employer đăng ký."""
    slug = generate_unique_company_slug(db, name)
    company = Company(
        name=name,
        slug=slug,
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
    if ("name" in changes and changes["name"]) or not company.slug:
        company.slug = generate_unique_company_slug(db, company.name, current_company_id=company.id)
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


def update_company_logo(db: Session, company: Company, logo_url: str, user_id: int | None = None) -> Company:
    """Cập nhật URL logo công ty và đưa về trạng thái chờ duyệt, gửi thông báo cho admin."""
    company.logo = logo_url
    company.logo_url = logo_url
    company.logo_status = "pending"
    if user_id:
        company.logo_uploaded_by = user_id
    company.logo_uploaded_at = datetime.utcnow()

    # Ghi thông báo cho Admin trong cùng transaction
    admins = db.scalars(select(User).where(User.role.in_(["admin", "operator"]), User.is_active == True)).all()
    for adm in admins:
        create_notification(
            db,
            user_id=adm.id,
            actor_id=user_id or company.employer_id,
            type=NotificationType.LOGO_PENDING,
            title="Logo công ty chờ duyệt",
            message=f"Công ty {company.name} vừa gửi logo chờ duyệt.",
            link="/pages/items.html?tab=logo_pending",
            ref_type="company_logo",
            ref_id=company.id,
        )

    db.commit()
    db.refresh(company)
    return company


def remove_company_logo(db: Session, company: Company) -> Company:
    """Gỡ logo công ty và chuyển trạng thái về removed."""
    company.logo = None
    company.logo_url = None
    company.logo_status = "removed"
    company.logo_uploaded_by = None
    company.logo_uploaded_at = None
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
