"""CRUD cho bảng companies."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company_schema import CompanyProfileUpdate


def create_draft_company(db: Session, *, name: str, employer_id: int) -> Company:
    """Tạo công ty nháp (is_draft=True) khi employer đăng ký."""
    company = Company(name=name, employer_id=employer_id, is_draft=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def get_company_by_employer(db: Session, employer_id: int) -> Company | None:
    """Lấy công ty theo employer_id (mỗi employer chỉ có 1 công ty)."""
    return db.scalar(select(Company).where(Company.employer_id == employer_id))


def update_company(db: Session, company: Company, data: CompanyProfileUpdate) -> Company:
    """Cập nhật thông tin hồ sơ công ty (chỉ các trường được gửi lên)."""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
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
