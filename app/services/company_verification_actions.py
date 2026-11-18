"""Các hành động Từ chối, Thu hồi, Đổi MST và Cổng kiểm tra quyền đăng tin (COMPANY_NOT_VERIFIED).
Giới hạn: <= 200 dòng.
"""
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyStatus
from app.models.company_verification import CompanyVerification
from app.models.job import Job
from app.models.user import User
from app.services.company_verification_rules import (
    normalize_and_validate_mst,
    raise_field_error,
    send_verification_email_safe,
    validate_reason_text,
)
from app.services.company_verification_service import (
    get_latest_verification,
    serialize_verification,
    write_verif_audit,
)
from app.services.notification import NotificationType, create_notification


def transition_open_jobs_to_reverify(db: Session, comp: Company) -> int:
    """Chuyển các tin đang mở của công ty sang trạng thái 'reverify_pending' (không xóa, không tự đóng)."""
    res = db.execute(
        update(Job)
        .where(
            (Job.company_id == comp.id) | ((Job.company_id.is_(None)) & (Job.employer_id == comp.employer_id)),
            Job.status.in_(["published", "pending", "OPEN", "PENDING"]),
        )
        .values(status="reverify_pending")
    )
    return int(res.rowcount or 0)


def reject_verification_request(
    db: Session, verif_id: int, actor: User, reason: str | None,
    expected_version: int | None = None, idempotency_key: str | None = None,
) -> dict:
    clean_reason = validate_reason_text(reason, "reason")
    verif = db.get(CompanyVerification, verif_id)
    if not verif:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy yêu cầu xác minh."})
    comp = db.get(Company, verif.company_id)
    if not comp:
        raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND", "message": "Không tìm thấy công ty."})

    if idempotency_key and verif.idempotency_key == idempotency_key and verif.status == "tu_choi":
        return serialize_verification(db, comp, verif)

    conds = [CompanyVerification.id == verif_id, CompanyVerification.status == "cho_duyet"]
    if expected_version is not None:
        conds.append(CompanyVerification.version == expected_version)

    res = db.execute(
        update(CompanyVerification).where(*conds).values(
            status="tu_choi", reviewed_by=actor.id, reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            rejection_reason=clean_reason, idempotency_key=idempotency_key, version=CompanyVerification.version + 1,
        )
    )
    if (res.rowcount or 0) == 0:
        raise_field_error(status.HTTP_409_CONFLICT, "CONCURRENT_OR_INVALID_STATE", "Yêu cầu này không còn ở trạng thái chờ duyệt hoặc đã được xử lý.")

    old_st = comp.verification_status
    comp.verification_status = "tu_choi"
    comp.status = CompanyStatus.REJECTED

    write_verif_audit(db, actor, "company_verification", verif.id, "reject_verification", old_st, "tu_choi", comp.name, clean_reason)

    msg = f"Công ty của bạn chưa được duyệt. Lý do: {clean_reason}. Gửi lại yêu cầu mới."
    create_notification(
        db, user_id=comp.employer_id, actor_id=actor.id, type=NotificationType.SYSTEM,
        title="Yêu cầu xác minh chưa được duyệt", message=msg,
        link="/pages/employer/company-settings.html", ref_type="company_verification", ref_id=verif.id,
        dedupe_key=f"company_verif:{verif.id}:tu_choi",
    )
    db.commit()
    db.refresh(comp)
    db.refresh(verif)
    owner = db.get(User, comp.employer_id)
    send_verification_email_safe(owner.email if owner else None, "[TechRecruit] Kết quả xác minh công ty", msg)
    return serialize_verification(db, comp, verif)


def revoke_company_verification(
    db: Session, company_id: int, actor: User, reason: str | None,
    expected_version: int | None = None, idempotency_key: str | None = None,
) -> dict:
    clean_reason = validate_reason_text(reason, "reason")
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND", "message": "Không tìm thấy công ty."})

    verif = get_latest_verification(db, comp.id)
    if idempotency_key and verif and verif.idempotency_key == idempotency_key and comp.verification_status == "thu_hoi":
        return serialize_verification(db, comp, verif)

    if comp.verification_status != "da_xac_minh":
        raise_field_error(status.HTTP_409_CONFLICT, "INVALID_STATE", "Chỉ có thể thu hồi đối với công ty đang ở trạng thái đã xác minh.")

    new_ver = 1
    if verif:
        conds = [CompanyVerification.id == verif.id]
        if expected_version is not None:
            conds.append(CompanyVerification.version == expected_version)
        res = db.execute(
            update(CompanyVerification).where(*conds).values(
                status="thu_hoi", reviewed_by=actor.id, reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                rejection_reason=clean_reason, idempotency_key=idempotency_key, version=CompanyVerification.version + 1,
            )
        )
        if (res.rowcount or 0) == 0:
            raise_field_error(status.HTTP_409_CONFLICT, "CONCURRENT_OR_INVALID_STATE", "Phiên bản dữ liệu đã thay đổi, vui lòng tải lại trước khi thu hồi.")
        db.refresh(verif)
        new_ver = verif.version

    old_st = comp.verification_status
    comp.verification_status = "thu_hoi"
    comp.status = CompanyStatus.REJECTED
    affected_jobs = transition_open_jobs_to_reverify(db, comp)

    write_verif_audit(
        db, actor, "company_verification", verif.id if verif else comp.id,
        "revoke_verification", old_st, f"thu_hoi (chuyển {affected_jobs} tin sang reverify_pending)", comp.name, clean_reason,
    )

    msg = f"Xác minh công ty của bạn đã bị thu hồi. Lý do: {clean_reason}. Các tin đang mở đã chuyển sang chờ xác minh lại."
    create_notification(
        db, user_id=comp.employer_id, actor_id=actor.id, type=NotificationType.SYSTEM,
        title="Thu hồi xác minh công ty", message=msg,
        link="/pages/employer/company-settings.html", ref_type="company", ref_id=comp.id,
        dedupe_key=f"company_verif:{comp.id}:thu_hoi:v{new_ver}",
    )
    db.commit()
    db.refresh(comp)
    owner = db.get(User, comp.employer_id)
    send_verification_email_safe(owner.email if owner else None, "[TechRecruit] Thông báo thu hồi xác minh công ty", msg)
    out = serialize_verification(db, comp, verif)
    out["affected_jobs_count"] = affected_jobs
    return out


def handle_employer_mst_update_if_changed(db: Session, comp: Company, actor: User, new_tax_raw: str | None) -> str | None:
    """Nếu nhà tuyển dụng cập nhật MST trên công ty đã xác minh: chuẩn hóa, chuyển về cho_duyet & đưa tin mở sang reverify_pending."""
    if new_tax_raw is None:
        return comp.tax_code
    trimmed = new_tax_raw.strip()
    if not trimmed:
        return comp.tax_code
    norm_mst = normalize_and_validate_mst(trimmed)
    if norm_mst != (comp.tax_code or "") and comp.verification_status == "da_xac_minh":
        old_mst = comp.tax_code
        comp.verification_status = "cho_duyet"
        comp.status = CompanyStatus.PENDING
        affected = transition_open_jobs_to_reverify(db, comp)
        write_verif_audit(
            db, actor, "company", comp.id, "mst_changed_reverify",
            f"da_xac_minh ({old_mst})", f"cho_duyet ({norm_mst}, {affected} tin chuyển chờ xác minh lại)", comp.name,
            "Nhà tuyển dụng thay đổi mã số thuế đã xác minh",
        )
    return norm_mst


def enforce_company_job_rule(
    db: Session, employer_id: int, target_status: str, *, is_creating: bool = False,
    existing_job: Job | None = None, new_deadline=None,
) -> Company | None:
    """Kiểm tra quy tắc đăng tin Bước 3: trả mã COMPANY_NOT_VERIFIED khi chưa ở da_xac_minh."""
    comp = db.scalar(select(Company).where(Company.employer_id == employer_id).order_by(Company.id.asc()))
    v_status = comp.verification_status if comp else "chua_xac_minh"

    # Khi công ty bị thu hồi: cấm tạo tin mới (kể cả nháp) và cấm gia hạn hạn nộp
    if v_status == "thu_hoi":
        if is_creating:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "COMPANY_NOT_VERIFIED", "message": "Công ty đã bị thu hồi xác minh nên không thể tạo tin tuyển dụng mới. Vui lòng gửi lại hồ sơ xác minh."},
            )
        if existing_job and new_deadline and existing_job.deadline and new_deadline > existing_job.deadline:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "COMPANY_NOT_VERIFIED", "message": "Không thể gia hạn hạn nộp hồ sơ khi công ty đang bị thu hồi xác minh."},
            )

    is_draft_target = str(target_status or "").strip().lower() == "draft"
    if not is_draft_target and v_status != "da_xac_minh":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "COMPANY_NOT_VERIFIED", "message": "Công ty chưa được xác minh nên chỉ có thể lưu nháp tin tuyển dụng."},
        )
    return comp
