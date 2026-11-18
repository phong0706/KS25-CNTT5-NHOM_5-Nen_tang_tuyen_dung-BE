"""Dịch vụ đánh giá tiêu chí xác thực nhà tuyển dụng từ dữ liệu thật & duyệt thủ công (<= 175 dòng)."""
from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.company_verification import CompanyVerification
from app.models.job import Job
from app.models.report import Report, ReportStatus
from app.models.user import User

CRITERION_META = {
    "license_and_tax": ("Giấy phép kinh doanh & Mã số thuế", "Hồ sơ xác minh công ty"),
    "domain_email": ("Email trùng tên miền website công ty", "Tài khoản & website công ty"),
    "account_age": ("Thời gian hoạt động tài khoản (tối thiểu 180 ngày)", "Ngày tạo tài khoản"),
    "no_open_reports": ("Không có báo cáo vi phạm đang mở", "Hệ thống báo cáo vi phạm"),
    "phone_verified": ("Xác thực số điện thoại liên hệ", "Trạng thái xác thực SĐT"),
}


def _extract_website_host(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        host = (urlparse(raw if "://" in raw else f"https://{raw}").hostname or "").lower().strip(".")
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def _serialize_log(log: AuditLog) -> dict:
    return {
        "id": log.id, "criterion_code": log.new_value,
        "criterion_label": CRITERION_META.get(log.new_value, (log.new_value or "", ""))[0],
        "actor_id": log.actor_id, "actor_name": log.actor_name, "actor_role": log.actor_role,
        "reason": log.reason or "", "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def evaluate_employer_criteria(db: Session, company: Company) -> dict:
    owner = db.get(User, company.employer_id) if company.employer_id else None
    latest_verif = db.scalar(select(CompanyVerification).where(CompanyVerification.company_id == company.id).order_by(CompanyVerification.id.desc()))
    job_ids_sub = select(Job.id).where(Job.company_id == company.id)
    open_reports = int(db.scalar(
        select(func.count(func.distinct(Report.id))).where(
            Report.status == ReportStatus.PENDING,
            or_(Report.employer_id == company.employer_id, Report.post_id.in_(job_ids_sub)),
        )
    ) or 0)
    audit_rows = db.scalars(
        select(AuditLog).where(
            AuditLog.target_type == "employer_criterion",
            AuditLog.target_id == company.id,
            AuditLog.action == "MANUAL_VERIFY_CRITERION",
        ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    ).all()
    manual_map = {}
    for r in audit_rows:
        if r.new_value and r.new_value not in manual_map:
            manual_map[r.new_value] = r

    now = datetime.now()
    vst = company.verification_status or ("da_xac_minh" if company.is_verified else "chua_xac_minh")
    lic_dt = (latest_verif.reviewed_at if latest_verif and latest_verif.reviewed_at else company.verified_at) or (latest_verif.submitted_at if latest_verif else company.updated_at)
    if vst == "da_xac_minh" or company.is_verified:
        c1 = ("dat", "Mã số thuế và giấy phép kinh doanh đã được kiểm tra và duyệt.", "")
    elif vst in ("tu_choi", "thu_hoi"):
        c1 = ("chua_dat", (latest_verif.rejection_reason if latest_verif and latest_verif.rejection_reason else "Hồ sơ xác minh đã bị từ chối hoặc thu hồi."), "Tải lại ảnh/PDF giấy phép rõ nét và đúng mã số thuế tại mục Xác minh công ty.")
    else:
        c1 = ("chua_kiem_tra", "Doanh nghiệp chưa hoàn tất duyệt giấy phép kinh doanh và mã số thuế.", "Nộp mã số thuế và tệp giấy phép kinh doanh để hoàn tất bước kiểm tra pháp nhân.")

    web_host = _extract_website_host(company.website)
    email_dom = owner.email.split("@", 1)[1].lower().strip() if (owner and owner.email and "@" in owner.email) else ""
    if not web_host:
        c2 = ("chua_kiem_tra", "Công ty chưa khai báo website nên chưa thể đối chiếu tên miền email.", "Cập nhật website chính thức của doanh nghiệp trong phần Thông tin doanh nghiệp.")
    elif not email_dom:
        c2 = ("chua_kiem_tra", "Không xác định được tên miền email tài khoản.", "Cập nhật email tài khoản doanh nghiệp theo tên miền công ty.")
    elif email_dom == web_host or email_dom.endswith(f".{web_host}"):
        c2 = ("dat", f"Email ({email_dom}) trùng khớp với tên miền website {web_host}.", "")
    else:
        c2 = ("chua_dat", f"Email tài khoản ({email_dom}) chưa khớp tên miền website ({web_host}).", f"Thêm email có đuôi {web_host} trong hồ sơ tài khoản.")

    if owner and owner.created_at:
        days = max(0, (now - owner.created_at.replace(tzinfo=None)).days)
        c3 = ("dat", f"Tài khoản đã hoạt động {days} ngày (đạt tối thiểu 180 ngày).", "") if days >= 180 else (
            "chua_dat", f"Tài khoản mới hoạt động {days}/180 ngày.",
            f"Duy trì hoạt động thêm {180 - days} ngày để đủ 6 tháng hoặc liên hệ quản trị viên duyệt thủ công.",
        )
    else:
        c3 = ("chua_kiem_tra", "Chưa có dữ liệu ngày tạo tài khoản.", "Kiểm tra lại thông tin tài khoản nhà tuyển dụng.")

    c4 = ("dat", "Không có báo cáo vi phạm nào đang chờ xử lý.", "") if open_reports == 0 else (
        "chua_dat", f"Hiện có {open_reports} báo cáo vi phạm đang mở chưa xử lý.", "Kiểm tra và xử lý xong toàn bộ báo cáo vi phạm đang mở.",
    )
    c5 = ("chua_kiem_tra", "Hệ thống chưa có cột xác thực số điện thoại (OTP) trong dữ liệu tài khoản.", "Đảm bảo số điện thoại liên hệ chính xác trong hồ sơ; quản trị viên có thể duyệt thủ công sau khi đối chiếu.")

    raw_items = [
        ("license_and_tax", c1, lic_dt),
        ("domain_email", c2, company.updated_at or now),
        ("account_age", c3, now if (owner and owner.created_at) else None),
        ("no_open_reports", c4, now),
        ("phone_verified", c5, None),
    ]
    criteria = []
    for code, (st, reason, hint), checked_dt in raw_items:
        label, source = CRITERION_META[code]
        m_log = manual_map.get(code)
        is_manual, manual_info = False, None
        if m_log:
            st, is_manual, checked_dt = "dat", True, m_log.created_at or checked_dt
            reason, hint = f"Đã duyệt thủ công bởi {m_log.actor_name}: {m_log.reason or ''}".strip(), ""
            manual_info = _serialize_log(m_log)
        criteria.append({
            "code": code, "label": label, "source": source, "status": st, "reason": reason, "action_hint": hint,
            "checked_at": checked_dt.isoformat() if (checked_dt and st != "chua_kiem_tra") else None,
            "is_manual": is_manual, "manual_approval": manual_info,
        })

    checked_items = [it for it in criteria if it["status"] in ("dat", "chua_dat")]
    passed_count = sum(1 for it in checked_items if it["status"] == "dat")
    checked_count = len(checked_items)
    return {
        "company_id": company.id, "company_name": company.name, "employer_id": company.employer_id,
        "employer_email": owner.email if owner else None,
        "summary_text": f"{passed_count} trên {checked_count} tiêu chí đạt." if checked_count > 0 else "Chưa có tiêu chí nào hoàn tất kiểm tra.",
        "passed_count": passed_count, "checked_count": checked_count,
        "unchecked_count": sum(1 for it in criteria if it["status"] == "chua_kiem_tra"),
        "total_criteria": len(criteria), "open_reports_count": open_reports,
        "criteria": criteria, "logs": [_serialize_log(r) for r in audit_rows],
    }


def manual_approve_criterion(db: Session, company_id: int, criterion_code: str, reason: str | None, actor: User) -> dict:
    if criterion_code not in CRITERION_META:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã tiêu chí không hợp lệ.")
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty.")
    clean_reason = (reason or "").strip()
    if len(clean_reason) < 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng nhập lý do duyệt thủ công (tối thiểu 5 ký tự).")
    db.add(AuditLog(
        actor_id=actor.id, actor_name=actor.full_name or actor.email, actor_role=actor.role,
        target_type="employer_criterion", target_id=comp.id, target_label=f"{comp.name} · {CRITERION_META[criterion_code][0]}",
        action="MANUAL_VERIFY_CRITERION", old_value=None, new_value=criterion_code, reason=clean_reason,
    ))
    db.commit()
    return evaluate_employer_criteria(db, comp)
