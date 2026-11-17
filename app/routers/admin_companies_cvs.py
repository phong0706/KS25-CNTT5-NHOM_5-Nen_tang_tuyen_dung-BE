"""Router Quản trị cấp cao: Công ty, Logo (PNG/WebP <= 200KB, <= 512px, strip metadata),
CV ứng viên (ghi nhật ký mỗi lần mở) và Nhật ký thay đổi (/api/admin/...).
Giới hạn: < 200 dòng.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.application import Application, CV
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.job import Job
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["Admin Companies & CVs Governance"])

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_LOGO_BYTES = 200 * 1024  # 200 KB
MAX_LOGO_DIM = 512  # 512 px


def _write_audit(
    db: Session,
    actor: User,
    target_type: str,
    target_id: int,
    action: str,
    old_val: str | None = None,
    new_val: str | None = None,
    target_label: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id,
        actor_name=actor.full_name or actor.email,
        actor_role=actor.role,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        action=action,
        old_value=old_val,
        new_value=new_val,
    )
    db.add(entry)
    return entry


def _full_logo_url(request: Request, rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    if rel_path.startswith("http://") or rel_path.startswith("https://"):
        return rel_path
    base = str(request.base_url).rstrip("/")
    return f"{base}{rel_path if rel_path.startswith('/') else '/' + rel_path}"


def _serialize_company(db: Session, request: Request, comp: Company, open_jobs: int = 0) -> dict:
    uploader_name = None
    if comp.logo_uploaded_by:
        u = db.get(User, comp.logo_uploaded_by)
        uploader_name = u.full_name if u else f"User #{comp.logo_uploaded_by}"
    owner = db.get(User, comp.employer_id) if comp.employer_id else None
    raw_path = comp.logo_url or comp.logo
    l_status = comp.logo_status or ("active" if raw_path else "missing")
    if not raw_path and l_status == "active":
        l_status = "missing"
    return {
        "id": comp.id,
        "name": comp.name,
        "slug": comp.slug,
        "employer_id": comp.employer_id,
        "employer_name": owner.full_name if owner else "Chưa gán",
        "employer_email": owner.email if owner else "",
        "tax_code": comp.tax_code,
        "size": comp.size or comp.company_size,
        "website": comp.website,
        "address": comp.address,
        "status": comp.status.value if hasattr(comp.status, "value") else str(comp.status),
        "open_jobs_count": int(open_jobs or 0),
        "logo_path": raw_path,
        "logo_full_url": _full_logo_url(request, raw_path),
        "logo_status": l_status,
        "logo_uploaded_by": comp.logo_uploaded_by,
        "logo_uploaded_by_name": uploader_name,
        "logo_uploaded_at": comp.logo_uploaded_at.isoformat() if comp.logo_uploaded_at else None,
        "updated_at": comp.updated_at.isoformat() if comp.updated_at else None,
    }


def _check_company_access(user: User, comp: Company):
    if user.role in ("admin", "operator"):
        return
    if user.role in ("employer", "recruiter") and comp.employer_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền truy cập hoặc chỉnh sửa thông tin công ty của người khác.",
    )


@router.get("/companies", summary="Danh sách công ty cho khu quản trị")
def list_admin_companies(
    request: Request,
    q: str = Query("", max_length=100),
    logo_status: str = Query("all"),
    current_user: User = Depends(role_required("admin", "operator")),
    db: Session = Depends(get_db),
):
    job_sub = (
        select(Job.company_id, func.count(Job.id).label("cnt"))
        .where(Job.status == "published")
        .group_by(Job.company_id)
        .subquery()
    )
    stmt = select(Company, func.coalesce(job_sub.c.cnt, 0).label("open_jobs")).outerjoin(
        job_sub, Company.id == job_sub.c.company_id
    )
    kw = q.strip()
    if kw:
        stmt = stmt.where(or_(Company.name.ilike(f"%{kw}%"), Company.slug.ilike(f"%{kw}%")))
    if logo_status in ("active", "removed", "missing"):
        stmt = stmt.where(Company.logo_status == logo_status)
    rows = db.execute(stmt.order_by(Company.id.asc())).all()
    items = [_serialize_company(db, request, r[0], int(r[1] or 0)) for r in rows]
    return {"items": items, "total": len(items), "viewer_role": current_user.role}


@router.get("/companies/{company_id}", summary="Chi tiết công ty kèm thông tin logo và quyền sở hữu")
def get_admin_company_detail(
    company_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty.")
    _check_company_access(current_user, comp)
    open_jobs = db.scalar(select(func.count(Job.id)).where(and_(Job.company_id == company_id, Job.status == "published"))) or 0
    return _serialize_company(db, request, comp, open_jobs)


@router.post("/companies/{company_id}/logo", summary="Upload/Thay logo công ty (PNG/WebP <= 200KB, <= 512px, xóa metadata)")
def upload_company_logo_admin(
    company_id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty.")
    _check_company_access(current_user, comp)

    raw_bytes = file.file.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="Tệp tải lên trống.")

    # 1. Kiểm tra magic bytes thật ở đầu file (từ chối .exe hoặc định dạng giả mạo)
    is_png = raw_bytes[:8] == PNG_MAGIC
    is_webp = len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP"
    if not (is_png or is_webp):
        raise HTTPException(
            status_code=422,
            detail="Sai định dạng tệp: Chỉ chấp nhận ảnh PNG hoặc WebP thật (kiểm tra chữ ký tệp không hợp lệ).",
        )

    # 2. Kiểm tra dung lượng tối đa 200 KB
    if len(raw_bytes) > MAX_LOGO_BYTES:
        kb = round(len(raw_bytes) / 1024, 1)
        raise HTTPException(
            status_code=413,
            detail=f"Dung lượng tệp vượt quá giới hạn: {kb} KB (tối đa cho phép 200 KB).",
        )

    # 3. Đọc ảnh & kiểm tra kích thước tối đa 512x512 px + xóa sạch metadata
    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            img.load()
            w, h = img.size
            if w > MAX_LOGO_DIM or h > MAX_LOGO_DIM:
                raise HTTPException(
                    status_code=422,
                    detail=f"Kích thước ảnh vượt quá giới hạn: {w}x{h} px (tối đa cho phép 512x512 px).",
                )
            # Tạo ảnh mới chỉ chứa dữ liệu điểm ảnh (xóa toàn bộ EXIF, ICC profile, tEXt chunks)
            mode = img.mode if img.mode in ("RGB", "RGBA") else "RGBA"
            converted = img.convert(mode)
            clean_img = Image.new(mode, converted.size)
            clean_img.putdata(list(converted.getdata()))
            out_buf = BytesIO()
            ext = ".png" if is_png else ".webp"
            fmt = "PNG" if is_png else "WEBP"
            clean_img.save(out_buf, format=fmt)
            clean_bytes = out_buf.getvalue()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Sai định dạng tệp: Không thể giải mã dữ liệu hình ảnh hợp lệ.")

    # 4. Lưu bằng tên file ngẫu nhiên do server tạo
    logos_dir = Path(settings.UPLOAD_DIR) / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    server_filename = f"logo_{comp.id}_{uuid.uuid4().hex[:12]}{ext}"
    (logos_dir / server_filename).write_bytes(clean_bytes)

    old_full = _full_logo_url(request, comp.logo_url or comp.logo)
    new_rel = f"/uploads/logos/{server_filename}"
    new_full = _full_logo_url(request, new_rel)
    action_type = "replace_logo" if (comp.logo_url or comp.logo) else "upload_logo"

    comp.logo = new_rel
    comp.logo_url = new_rel
    comp.logo_status = "active"
    comp.logo_uploaded_by = current_user.id
    comp.logo_uploaded_at = datetime.utcnow()

    _write_audit(db, current_user, "company_logo", comp.id, action_type, old_full, new_full, comp.name)
    db.commit()
    db.refresh(comp)

    open_jobs = db.scalar(select(func.count(Job.id)).where(and_(Job.company_id == comp.id, Job.status == "published"))) or 0
    res = _serialize_company(db, request, comp, open_jobs)
    res["old_logo_full_url"] = old_full
    return res
