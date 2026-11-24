"""Dependency xác định phạm vi công ty duy nhất của nhà tuyển dụng (get_employer_scope)."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyStatus
from app.models.user import User


@dataclass(frozen=True)
class EmployerScope:
    user: User
    user_id: int
    company_id: int
    company: Company


def resolve_company_review_status(company: Company) -> str:
    """Trả về mã trạng thái chuẩn hóa của doanh nghiệp (không trả chuỗi nhãn)."""
    verif = (getattr(company, "verification_status", None) or "").strip().lower()
    if verif in ("da_xac_minh", "cho_duyet", "tu_choi", "thu_hoi", "chua_xac_minh"):
        if verif == "chua_xac_minh" and (company.is_verified or company.status == CompanyStatus.VERIFIED):
            return "da_xac_minh"
        return verif
    if company.is_verified or company.status == CompanyStatus.VERIFIED:
        return "da_xac_minh"
    if company.status == CompanyStatus.REJECTED:
        return "tu_choi"
    return "cho_duyet" if not company.is_draft else "chua_xac_minh"


def is_company_verified(company: Company) -> bool:
    return resolve_company_review_status(company) == "da_xac_minh"


def find_employer_company(db: Session, user_id: int) -> Company | None:
    """Tìm đúng 1 công ty thuộc quyền sở hữu của user_id (ưu tiên đã duyệt, không nháp)."""
    stmt = (
        select(Company)
        .where(Company.employer_id == user_id)
        .order_by(
            case((Company.verification_status == "da_xac_minh", 0), else_=1),
            case((Company.is_draft == False, 0), else_=1),  # noqa: E712
            Company.id.asc(),
        )
    )
    return db.scalars(stmt).first()


def get_employer_scope(
    current_user: User = Depends(role_required("employer", "recruiter")),
    db: Session = Depends(get_db),
) -> EmployerScope:
    """Trả về company_id đã duyệt của nhà tuyển dụng đang đăng nhập; lỗi -> 409."""
    company = find_employer_company(db, current_user.id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "COMPANY_REQUIRED",
                "message": "Tài khoản chưa liên kết hồ sơ công ty. Vui lòng tạo hồ sơ doanh nghiệp trong Cài đặt công ty.",
            },
        )
    review_st = resolve_company_review_status(company)
    if review_st != "da_xac_minh":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "COMPANY_NOT_VERIFIED",
                "review_status": review_st,
                "message": "Hồ sơ doanh nghiệp chưa được phê duyệt. Vui lòng hoàn tất xác minh pháp nhân trong Cài đặt công ty.",
            },
        )
    return EmployerScope(
        user=current_user,
        user_id=current_user.id,
        company_id=company.id,
        company=company,
    )


def get_admin_company_scope(
    company_id: int = Query(..., ge=1, description="ID công ty cần xem"),
    current_user: User = Depends(role_required("admin", "operator")),
    db: Session = Depends(get_db),
) -> EmployerScope:
    """Chế độ dành cho Admin/Operator: xem theo company_id chỉ định rõ ràng và ghi AuditLog."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty.")
    db.add(
        AuditLog(
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            actor_role=current_user.role,
            target_type="company",
            target_id=company.id,
            target_label=company.name,
            action="view_employer_dashboard",
            new_value=f"company_id={company.id}",
        )
    )
    db.commit()
    return EmployerScope(
        user=current_user,
        user_id=current_user.id,
        company_id=company.id,
        company=company,
    )
