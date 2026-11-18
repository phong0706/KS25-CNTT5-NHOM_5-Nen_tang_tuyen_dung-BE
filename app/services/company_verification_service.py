"""Dịch vụ nghiệp vụ Xác minh công ty: lưu trữ riêng tư, xử lý duyệt / từ chối / thu hồi
có khóa lạc quan (version), ghi audit_logs và phát thông báo trong ứng dụng.
Giới hạn: <= 200 dòng.
"""
from datetime import datetime
from pathlib import Path
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyStatus
from app.models.company_verification import CompanyVerification
from app.models.job import Job
from app.models.user import User
from app.services.company_verification_rules import (
    VERIF_STATUS_LABELS,
    VERIF_STATUS_SENTENCES,
    normalize_and_validate_mst,
    raise_field_error,
    send_verification_email_safe,
    validate_license_file_bytes,
    validate_reason_text,
)
from app.services.notification import NotificationType, create_notification

LICENSE_PRIVATE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "company_licenses"
LICENSE_PRIVATE_DIR.mkdir(parents=True, exist_ok=True)


def write_verif_audit(
    db: Session, actor: User, target_type: str, target_id: int, action: str,
    old_val: str | None, new_val: str | None, label: str | None = None, reason: str | None = None,
) -> None:
    db.add(AuditLog(
        actor_id=actor.id, actor_name=actor.full_name or actor.email, actor_role=actor.role,
        target_type=target_type, target_id=target_id, target_label=label,
        action=action, old_value=old_val, new_value=new_val, reason=reason,
    ))


def serialize_verification(db: Session, comp: Company, verif: CompanyVerification | None) -> dict:
    v_status = comp.verification_status or "chua_xac_minh"
    sub_user = db.get(User, verif.submitted_by) if (verif and verif.submitted_by) else None
    rev_user = db.get(User, verif.reviewed_by) if (verif and verif.reviewed_by) else None
    return {
        "company_id": comp.id,
        "company_name": comp.name,
        "tax_code": comp.tax_code,
        "verification_status": v_status,
        "status_label": VERIF_STATUS_LABELS.get(v_status, v_status),
        "status_sentence": VERIF_STATUS_SENTENCES.get(v_status, ""),
        "can_publish_jobs": v_status == "da_xac_minh",
        "request": None if not verif else {
            "id": verif.id,
            "mst": verif.mst,
            "status": verif.status,
            "license_original_name": verif.license_original_name,
            "license_mime_type": verif.license_mime_type,
            "license_size_bytes": verif.license_size_bytes,
            "submitted_by": verif.submitted_by,
            "submitted_by_name": sub_user.full_name if sub_user else f"User #{verif.submitted_by}",
            "reviewed_by": verif.reviewed_by,
            "reviewed_by_name": (rev_user.full_name if rev_user else None),
            "rejection_reason": verif.rejection_reason,
            "submitted_at": verif.submitted_at.isoformat() if verif.submitted_at else None,
            "reviewed_at": verif.reviewed_at.isoformat() if verif.reviewed_at else None,
            "version": verif.version,
        },
    }


def get_latest_verification(db: Session, company_id: int) -> CompanyVerification | None:
    return db.scalar(
        select(CompanyVerification)
        .where(CompanyVerification.company_id == company_id)
        .order_by(CompanyVerification.id.desc())
        .limit(1)
    )


def submit_verification_request(
    db: Session, comp: Company, actor: User, raw_mst: str, orig_filename: str | None, raw_bytes: bytes,
) -> dict:
    existing_pending = db.scalar(
        select(CompanyVerification.id).where(CompanyVerification.company_id == comp.id, CompanyVerification.status == "cho_duyet")
    )
    if existing_pending is not None:
        raise_field_error(
            status.HTTP_409_CONFLICT,
            "VERIFICATION_ALREADY_PENDING",
            "Công ty đang có một yêu cầu xác minh chờ duyệt. Vui lòng đợi kết quả xét duyệt trước khi gửi yêu cầu mới.",
        )

    norm_mst = normalize_and_validate_mst(raw_mst)
    mime_type, ext = validate_license_file_bytes(raw_bytes)

    LICENSE_PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    storage_key = f"lic_{comp.id}_{uuid.uuid4().hex}{ext}"
    (LICENSE_PRIVATE_DIR / storage_key).write_bytes(raw_bytes)

    old_st = comp.verification_status or "chua_xac_minh"
    verif = CompanyVerification(
        company_id=comp.id, mst=norm_mst, mst_raw=str(raw_mst).strip()[:50],
        status="cho_duyet", license_storage_key=storage_key,
        license_original_name=(orig_filename or f"giay_phep{ext}")[:255],
        license_mime_type=mime_type, license_size_bytes=len(raw_bytes),
        submitted_by=actor.id, version=1,
    )
    comp.verification_status = "cho_duyet"
    comp.status = CompanyStatus.PENDING
    comp.tax_code = norm_mst

    try:
        db.add(verif)
        db.flush()
    except IntegrityError:
        db.rollback()
        (LICENSE_PRIVATE_DIR / storage_key).unlink(missing_ok=True)
        raise_field_error(status.HTTP_409_CONFLICT, "VERIFICATION_ALREADY_PENDING", "Công ty đang có yêu cầu xác minh chờ duyệt.")

    write_verif_audit(db, actor, "company_verification", verif.id, "submit_verification", old_st, "cho_duyet", comp.name)

    admins = db.scalars(select(User).where(User.role.in_(["admin", "operator"]), User.is_active == True)).all()  # noqa: E712
    for adm in admins:
        create_notification(
            db, user_id=adm.id, actor_id=actor.id, type=NotificationType.SYSTEM,
            title="Yêu cầu xác minh công ty mới",
            message=f"Doanh nghiệp {comp.name} vừa gửi hồ sơ xác minh pháp nhân chờ xét duyệt.",
            link="/pages/admin/companies.html?verif_status=cho_duyet",
            ref_type="company_verification", ref_id=verif.id,
            dedupe_key=f"company_verif:{verif.id}:submitted",
        )
    db.commit()
    db.refresh(comp)
    db.refresh(verif)
    return serialize_verification(db, comp, verif)


def approve_verification_request(
    db: Session, verif_id: int, actor: User, expected_version: int | None = None, idempotency_key: str | None = None,
) -> dict:
    verif = db.get(CompanyVerification, verif_id)
    if not verif:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy yêu cầu xác minh."})
    comp = db.get(Company, verif.company_id)
    if not comp:
        raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND", "message": "Không tìm thấy công ty."})

    if idempotency_key and verif.idempotency_key == idempotency_key and verif.status == "da_xac_minh":
        return serialize_verification(db, comp, verif)

    conds = [CompanyVerification.id == verif_id, CompanyVerification.status == "cho_duyet"]
    if expected_version is not None:
        conds.append(CompanyVerification.version == expected_version)

    now = datetime.utcnow()
    res = db.execute(
        update(CompanyVerification).where(*conds).values(
            status="da_xac_minh", reviewed_by=actor.id, reviewed_at=now,
            rejection_reason=None, idempotency_key=idempotency_key, version=CompanyVerification.version + 1,
        )
    )
    if (res.rowcount or 0) == 0:
        raise_field_error(status.HTTP_409_CONFLICT, "CONCURRENT_OR_INVALID_STATE", "Yêu cầu này đã được xử lý hoặc phiên bản dữ liệu đã thay đổi.")

    old_st = comp.verification_status
    comp.verification_status = "da_xac_minh"
    comp.status = CompanyStatus.VERIFIED
    comp.tax_code = verif.mst
    comp.is_draft = False

    db.execute(update(Job).where(Job.company_id == comp.id, Job.status == "reverify_pending").values(status="published"))
    write_verif_audit(db, actor, "company_verification", verif.id, "approve_verification", old_st, "da_xac_minh", comp.name)

    msg = f"Công ty {comp.name} đã được duyệt xác minh pháp nhân. Bạn có thể đăng tin tuyển dụng ngay bây giờ."
    create_notification(
        db, user_id=comp.employer_id, actor_id=actor.id, type=NotificationType.SYSTEM,
        title="Công ty đã được xác minh", message=msg,
        link="/pages/employer/company-settings.html", ref_type="company_verification", ref_id=verif.id,
        dedupe_key=f"company_verif:{verif.id}:da_xac_minh",
    )
    db.commit()
    db.refresh(comp)
    db.refresh(verif)
    owner = db.get(User, comp.employer_id)
    send_verification_email_safe(owner.email if owner else None, "[TechRecruit] Kết quả xác minh công ty", msg)
    return serialize_verification(db, comp, verif)
