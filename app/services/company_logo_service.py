"""Dịch vụ xử lý, xác thực và lưu trữ logo công ty (PNG/WebP, <= 200 KB, <= 512x512px)."""
import io
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
from PIL import Image
from app.core.config import settings

MAX_LOGO_BYTES = 200 * 1024  # 200 KB
MAX_LOGO_DIM = 512  # 512 px
ALLOWED_LOGO_EXTS = {".png", ".webp"}
ALLOWED_LOGO_MIMES = {"image/png", "image/webp"}


def validate_and_save_company_logo(file: UploadFile, company_id: int) -> str:
    """Kiểm tra magic bytes, kích thước, dung lượng và lưu logo an toàn (loại bỏ metadata)."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_LOGO_EXTS or file.content_type not in ALLOWED_LOGO_MIMES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Chỉ chấp nhận file ảnh định dạng PNG hoặc WebP")

    content = file.file.read()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File ảnh không được để trống")
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Ảnh vượt quá dung lượng cho phép (tối đa 200 KB)")

    try:
        probe = Image.open(io.BytesIO(content))
        probe.verify()
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File không đúng định dạng PNG hoặc WebP hợp lệ")

    im = Image.open(io.BytesIO(content))
    if im.format not in ("PNG", "WEBP"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File không đúng định dạng PNG hoặc WebP hợp lệ")
    if im.width > MAX_LOGO_DIM or im.height > MAX_LOGO_DIM:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Kích thước ảnh không được vượt quá {MAX_LOGO_DIM}x{MAX_LOGO_DIM} px")

    dest_dir = Path(settings.UPLOAD_DIR) / "logos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = ".png" if im.format == "PNG" else ".webp"
    unique_name = f"logo_{company_id}_{uuid.uuid4().hex[:12]}{ext}"
    dest_path = dest_dir / unique_name

    # Lưu ảnh sạch loại bỏ EXIF / metadata
    clean_im = Image.new(im.mode, im.size)
    clean_im.paste(im)
    clean_im.save(dest_path, format=im.format, optimize=True)

    return f"/uploads/logos/{unique_name}"
