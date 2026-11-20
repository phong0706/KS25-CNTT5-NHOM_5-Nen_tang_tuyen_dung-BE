"""Dịch vụ quản lý vòng đời và đồng bộ logo công ty (Company Logo Service).
Tuân thủ techrecruit-rules: <= 200 dòng, transaction an toàn, kiểm tra nội dung thật.
"""
from datetime import datetime, timezone
import time, uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.job import Job
from app.models.user import User
from app.services.logo_processing import LogoError, process_logo
from app.services.notification import NotificationType, create_notification

_HOME_COMPANIES_CACHE: Optional[tuple[float, List[Dict[str, Any]]]] = None
HOME_CACHE_TTL = 60

ERROR_MAP = {
    "too_large": (status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Dung lượng ảnh vượt quá giới hạn 2MB. Vui lòng chọn tệp nhỏ hơn."),
    "unsupported_format": (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Định dạng không được hỗ trợ. Chỉ chấp nhận ảnh PNG, JPEG hoặc WebP."),
    "not_logo_shape": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Ảnh giống banner. Hãy cắt riêng biểu tượng công ty rồi tải lại."),
    "too_small": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Ảnh biểu tượng quá nhỏ (cạnh ngắn tối thiểu 48px sau khi cắt viền). Vui lòng tải ảnh rõ nét hơn."),
    "empty_file": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Tệp ảnh rỗng hoặc không có dữ liệu."),
    "blank_image": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Ảnh toàn một màu hoặc trong suốt, không tìm thấy biểu tượng logo."),
    "decompression_bomb": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Ảnh có kích thước điểm ảnh vượt ngưỡng an toàn cho phép."),
}


def clear_home_companies_cache():
    global _HOME_COMPANIES_CACHE
    _HOME_COMPANIES_CACHE = None


def handle_logo_error(err: LogoError) -> None:
    code, msg = ERROR_MAP.get(err.code, (status.HTTP_422_UNPROCESSABLE_ENTITY, "Tệp ảnh bị lỗi hoặc không thể đọc được."))
    raise HTTPException(code, msg)


def generate_logo_filename(company_id: int, version: int, ext: str) -> str:
    return f"logo_{company_id}_v{version}_{uuid.uuid4().hex[:8]}{ext}"


def validate_logo_file(content: bytes, filename: str) -> str:
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(422, "File rỗng hoặc vượt quá 2MB.")
    import io
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(content))
        im.verify()
        fmt = (im.format or "").upper()
        ext_map = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
        if fmt not in ext_map:
            raise HTTPException(422, "Định dạng không được hỗ trợ.")
        ext = ext_map[fmt]
        fn = filename.lower()
        if not fn.endswith(ext) and not (fmt == "JPEG" and fn.endswith((".jpg", ".jpeg"))):
            raise HTTPException(422, "Đuôi file không khớp định dạng ảnh.")
        return ext
    except Exception:
        raise HTTPException(422, "Định dạng ảnh không hợp lệ.")


def save_processed_files(processed: dict[int, bytes]) -> tuple[str, str]:
    logo_dir = Path(settings.UPLOAD_DIR) / "logos"
    logo_dir.mkdir(parents=True, exist_ok=True)
    fid = uuid.uuid4().hex
    k256, k512 = f"{fid}_256.webp", f"{fid}_512.webp"
    with open(logo_dir / k256, "wb") as f1, open(logo_dir / k512, "wb") as f2:
        f1.write(processed[256])
        f2.write(processed[512])
    return k256, k512


def upload_company_logo(db: Session, company_id: int, content: bytes, user_id: int) -> CompanyLogo:
    comp = db.query(Company).filter_by(id=company_id).first()
    if not comp:
        raise HTTPException(404, "Không tìm thấy công ty.")
    try:
        processed = process_logo(content)
    except LogoError as e:
        handle_logo_error(e)

    k256, k512 = save_processed_files(processed)
    max_ver = db.query(func.max(CompanyLogo.version)).filter_by(company_id=company_id).scalar() or comp.logo_version or 0
    next_ver = max_ver + 1
    new_logo = CompanyLogo(
        company_id=company_id, file_key=k256, file_key_2x=k512,
        version=next_ver, status="cho_duyet", is_current=False, uploaded_by=user_id,
    )
    db.add(new_logo)
    comp.logo_status = "pending"
    db.flush()

    admins = db.scalars(select(User).where(User.role.in_(["admin", "operator"]), User.is_active == True)).all()  # noqa: E712
    for adm in admins:
        create_notification(
            db, user_id=adm.id, actor_id=user_id, type=NotificationType.SYSTEM,
            title="Yêu cầu duyệt logo công ty",
            message=f"Doanh nghiệp {comp.name} vừa tải lên logo mới chờ xét duyệt.",
            link=f"/pages/admin/companies.html?company={comp.id}&logo_status=pending",
            ref_type="company_logo", ref_id=new_logo.id,
            dedupe_key=f"company_logo:{new_logo.id}:submitted",
        )
    db.commit()
    db.refresh(new_logo)
    db.refresh(comp)
    clear_home_companies_cache()
    return new_logo


def apply_processed_logo(db: Session, comp: Company, processed: dict[int, bytes], actor_id: int | None = None) -> CompanyLogo:
    k256, k512 = save_processed_files(processed)
    db.query(CompanyLogo).filter_by(company_id=comp.id, is_current=True).update({"is_current": False, "status": "da_thay"})
    next_ver = (comp.logo_version or 1) + 1
    logo = CompanyLogo(
        company_id=comp.id, file_key=k256, file_key_2x=k512, version=next_ver,
        status="dang_dung", is_current=True, uploaded_by=actor_id, reviewed_by=actor_id,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(logo)
    comp.logo_url = f"/uploads/logos/{k256}"
    comp.logo_url_2x = f"/uploads/logos/{k512}"
    comp.logo, comp.logo_status, comp.logo_version = comp.logo_url, "active", next_ver
    db.commit()
    db.refresh(comp)
    db.refresh(logo)
    clear_home_companies_cache()
    return logo


def approve_company_logo(db: Session, logo_id: int, actor_id: int, actor_name: str, actor_role: str) -> CompanyLogo:
    logo = db.query(CompanyLogo).filter_by(id=logo_id).first()
    if not logo:
        raise HTTPException(404, "Không tìm thấy logo yêu cầu.")
    if logo.is_current and logo.status == "dang_dung":
        return logo
    newer = db.query(CompanyLogo).filter(
        CompanyLogo.company_id == logo.company_id, CompanyLogo.status == "cho_duyet", CompanyLogo.version > logo.version,
    ).first()
    if newer:
        raise HTTPException(409, "Có bản logo mới hơn đang chờ duyệt.")
    comp = db.query(Company).filter_by(id=logo.company_id).first()
    if not comp:
        raise HTTPException(404, "Không tìm thấy thông tin công ty.")

    db.query(CompanyLogo).filter_by(company_id=logo.company_id, is_current=True).update({"is_current": False, "status": "da_thay"})
    logo.is_current, logo.status, logo.reviewed_by = True, "dang_dung", actor_id
    logo.reviewed_at = datetime.now(timezone.utc)
    comp.logo_version = max((comp.logo_version or 1) + 1, logo.version)
    comp.logo_url = f"/uploads/logos/{logo.file_key}"
    comp.logo_url_2x = f"/uploads/logos/{logo.file_key_2x}" if logo.file_key_2x else None
    comp.logo, comp.logo_status = comp.logo_url, "active"

    db.add(AuditLog(
        actor_id=actor_id, actor_name=actor_name, actor_role=actor_role,
        target_type="company_logo", target_id=logo.id, target_label=comp.name,
        action="approve_logo", new_value=comp.logo_url,
    ))
    emp_uid = comp.owner_id or comp.employer_id
    if emp_uid:
        create_notification(
            db, user_id=emp_uid, actor_id=actor_id, type=NotificationType.SYSTEM,
            title="Logo công ty đã được phê duyệt",
            message=f"Logo của {comp.name} đã được phê duyệt và hiển thị công khai.",
            link="/pages/employer/recruitment.html", ref_type="company_logo", ref_id=logo.id,
            dedupe_key=f"company_logo:{logo.id}:approved",
        )
    db.commit()
    db.refresh(logo)
    clear_home_companies_cache()
    return logo


def reject_company_logo(db: Session, logo_id: int, reason: str, actor_id: int, actor_name: str, actor_role: str) -> CompanyLogo:
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(422, "Lý do từ chối phải có tối thiểu 10 ký tự.")
    logo = db.query(CompanyLogo).filter_by(id=logo_id).first()
    if not logo:
        raise HTTPException(404, "Không tìm thấy logo yêu cầu.")
    comp = db.query(Company).filter_by(id=logo.company_id).first()
    logo.status, logo.reject_reason = "tu_choi", reason.strip()
    logo.reviewed_by, logo.reviewed_at = actor_id, datetime.now(timezone.utc)
    if comp:
        has_pending = db.query(CompanyLogo).filter(CompanyLogo.company_id == comp.id, CompanyLogo.id != logo.id, CompanyLogo.status == "cho_duyet").first()
        comp.logo_status = "pending" if has_pending else ("active" if comp.logo_url else "missing")
        emp_uid = comp.owner_id or comp.employer_id
        if emp_uid:
            create_notification(
                db, user_id=emp_uid, actor_id=actor_id, type=NotificationType.SYSTEM,
                title="Logo công ty bị từ chối", message=f"Yêu cầu duyệt logo của {comp.name} bị từ chối: {reason.strip()}",
                link="/pages/employer/recruitment.html", ref_type="company_logo", ref_id=logo.id,
                dedupe_key=f"company_logo:{logo.id}:rejected",
            )
    db.add(AuditLog(
        actor_id=actor_id, actor_name=actor_name, actor_role=actor_role,
        target_type="company_logo", target_id=logo.id, target_label=comp.name if comp else None,
        action="reject_logo", reason=reason.strip(),
    ))
    db.commit()
    db.refresh(logo)
    return logo


def remove_company_logo(db: Session, company_id: int, actor_id: int, actor_name: str, actor_role: str) -> Company:
    comp = db.query(Company).filter_by(id=company_id).first()
    if not comp:
        raise HTTPException(404, "Không tìm thấy công ty.")
    db.query(CompanyLogo).filter_by(company_id=company_id, is_current=True).update({"is_current": False, "status": "da_thay"})
    comp.logo_url, comp.logo_url_2x, comp.logo, comp.logo_status = None, None, None, "missing"
    comp.logo_version = (comp.logo_version or 1) + 1
    db.add(AuditLog(
        actor_id=actor_id, actor_name=actor_name, actor_role=actor_role,
        target_type="company", target_id=comp.id, target_label=comp.name, action="remove_logo",
    ))
    db.commit()
    db.refresh(comp)
    clear_home_companies_cache()
    return comp


def get_home_companies(db: Session) -> List[Dict[str, Any]]:
    global _HOME_COMPANIES_CACHE
    now = time.time()
    if _HOME_COMPANIES_CACHE and (now - _HOME_COMPANIES_CACHE[0] < HOME_CACHE_TTL):
        return _HOME_COMPANIES_CACHE[1]
    stmt = (
        select(Company.id, Company.name, Company.slug, Company.logo_version, CompanyLogo.file_key, CompanyLogo.file_key_2x, func.count(Job.id).label("open_jobs"))
        .outerjoin(CompanyLogo, and_(CompanyLogo.company_id == Company.id, CompanyLogo.is_current == True))
        .join(Job, and_(Job.company_id == Company.id, Job.status == "published", or_(Job.deadline.is_(None), Job.deadline >= func.curdate())))
        .where(Company.is_visible == True, Company.is_draft == False, Company.verification_status == "da_xac_minh")
        .group_by(Company.id, Company.name, Company.slug, Company.logo_version, CompanyLogo.file_key, CompanyLogo.file_key_2x)
        .having(func.count(Job.id) > 0).order_by(func.count(Job.id).desc(), Company.id.asc())
    )
    rows = db.execute(stmt).all()
    res = [
        {"id": r.id, "name": r.name, "slug": r.slug, "open_jobs": int(r.open_jobs), "logo_version": r.logo_version,
         "logo_url": f"/uploads/logos/{r.file_key}?v={r.logo_version}" if r.file_key else None,
         "logo_url_2x": f"/uploads/logos/{r.file_key_2x}?v={r.logo_version}" if r.file_key_2x else None}
        for r in rows
    ]
    _HOME_COMPANIES_CACHE = (now, res)
    return res
