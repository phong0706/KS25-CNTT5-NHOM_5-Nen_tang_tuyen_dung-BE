"""CRUD cho bảng companies."""
from sqlalchemy.orm import Session

from app.models.company import Company


def create_draft_company(db: Session, *, name: str, employer_id: int) -> Company:
    """Tạo công ty nháp (is_draft=True) khi employer đăng ký."""
    company = Company(name=name, employer_id=employer_id, is_draft=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
