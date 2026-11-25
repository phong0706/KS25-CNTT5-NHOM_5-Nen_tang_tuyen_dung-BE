"""Quy tắc thuần cho Xác minh công ty: chuẩn hóa MST, kiểm tra magic bytes giấy phép,
kiểm tra lý do từ chối/thu hồi và gửi email an toàn (không chứa MST đầy đủ).
Giới hạn: <= 200 dòng.
"""
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger("app.services.company_verification")

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPG_MAGIC = b"\xff\xd8\xff"
PDF_MAGIC = b"%PDF-"
MAX_LICENSE_BYTES = 5 * 1024 * 1024  # 5 MB

VERIF_STATUS_LABELS: dict[str, str] = {
    "chua_xac_minh": "Chưa xác minh",
    "cho_duyet": "Đang chờ duyệt",
    "da_xac_minh": "Đã xác minh",
    "tu_choi": "Chưa được duyệt",
    "thu_hoi": "Đã thu hồi xác minh",
}

VERIF_STATUS_SENTENCES: dict[str, str] = {
    "chua_xac_minh": "Chưa xác minh. Bạn chỉ có thể lưu nháp tin tuyển dụng.",
    "cho_duyet": "Hồ sơ xác minh đang chờ ban quản trị xét duyệt. Trong thời gian này bạn chỉ có thể lưu nháp tin tuyển dụng.",
    "da_xac_minh": "Công ty đã được xác minh pháp nhân. Bạn có toàn quyền đăng và quản lý tin tuyển dụng.",
    "tu_choi": "Yêu cầu xác minh chưa được duyệt. Bạn chỉ có thể lưu nháp tin tuyển dụng cho đến khi gửi lại hồ sơ hợp lệ.",
    "thu_hoi": "Xác minh công ty đã bị thu hồi. Các tin đang mở đã chuyển sang chờ xác minh lại và bạn không thể đăng tin mới.",
}


def raise_field_error(http_code: int, code: str, message: str, field: str | None = None) -> None:
    payload = {"code": code, "message": message}
    if field:
        payload["field"] = field
    raise HTTPException(status_code=http_code, detail=payload)


def normalize_and_validate_mst(raw_mst: str | None) -> str:
    """Chuẩn hóa MST (bỏ khoảng trắng & dấu gạch thừa), kiểm tra đúng 10 số hoặc 10 số kèm '-' và 3 số chi nhánh."""
    if raw_mst is None or not str(raw_mst).strip():
        raise_field_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_MST", "Vui lòng nhập mã số thuế doanh nghiệp.", "mst")

    compact = re.sub(r"\s+", "", str(raw_mst))
    if not re.fullmatch(r"[0-9-]+", compact):
        raise_field_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_MST",
            "Mã số thuế không hợp lệ: chỉ được nhập chữ số (0-9) và dấu gạch nối (-).",
            "mst",
        )

    if re.fullmatch(r"\d{10}-\d{3}", compact):
        return compact

    digits = compact.replace("-", "")
    if len(digits) == 10:
        if "-" in compact and not re.fullmatch(r"\d+(-\d+)*", compact):
            raise_field_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_MST", "Dấu gạch nối trong mã số thuế không đúng vị trí.", "mst")
        return digits

    if len(digits) == 13:
        if "-" in compact:
            raise_field_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_MST",
                "Mã chi nhánh 13 số phải đặt dấu '-' ngay sau 10 chữ số chính (ví dụ: 0101248141-001).",
                "mst",
            )
        return f"{digits[:10]}-{digits[10:]}"

    raise_field_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_MST",
        f"Mã số thuế sai định dạng (hiện có {len(digits)} chữ số). Cần nhập đúng 10 chữ số hoặc 10 chữ số kèm '-' và 3 số chi nhánh (ví dụ: 0101248141 hoặc 0101248141-001).",
        "mst",
    )
    return ""


def validate_license_file_bytes(raw_bytes: bytes, max_bytes: int = MAX_LICENSE_BYTES) -> tuple[str, str]:
    """Kiểm tra dung lượng <= 5 MB và chữ ký magic bytes thật cho JPG, PNG, PDF."""
    if not raw_bytes:
        raise_field_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "EMPTY_LICENSE_FILE", "Tệp giấy phép tải lên đang trống.", "file")
    if len(raw_bytes) > max_bytes:
        mb = round(len(raw_bytes) / (1024 * 1024), 2)
        raise_field_error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "LICENSE_TOO_LARGE",
            f"Dung lượng tệp ({mb} MB) vượt quá giới hạn tối đa 5 MB. Hãy nén ảnh hoặc xuất bản PDF nhỏ hơn 5 MB.",
            "file",
        )
    if raw_bytes[:8] == PNG_MAGIC:
        return "image/png", ".png"
    if raw_bytes[:3] == JPG_MAGIC:
        return "image/jpeg", ".jpg"
    if raw_bytes[:5] == PDF_MAGIC:
        return "application/pdf", ".pdf"

    raise_field_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_LICENSE_FILE",
        "Định dạng tệp không hợp lệ (chữ ký tệp không khớp). Chỉ chấp nhận tệp JPG, PNG hoặc PDF thật, tối đa 5 MB.",
        "file",
    )
    return "", ""


def validate_reason_text(reason: str | None, field_name: str = "reason") -> str:
    clean = (reason or "").strip()
    if len(clean) < 10:
        raise_field_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "REASON_TOO_SHORT",
            "Vui lòng nhập lý do cụ thể tối thiểu 10 ký tự.",
            field_name,
        )
    return clean


def send_verification_email_safe(to_email: str | None, subject: str, body_text: str) -> bool:
    """Gửi email nếu SMTP đã được cấu hình sẵn; không chứa MST đầy đủ; lỗi email không ảnh hưởng thông báo trong app."""
    if not to_email or not settings.SMTP_HOST or not settings.SMTP_USER:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email
        safe_html = f"<p>{body_text}</p>"
        msg.attach(MIMEText(safe_html, "html", "utf-8"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=8) as s:
            s.starttls()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gửi email xác minh thất bại (bỏ qua an toàn): %s", exc)
        return False
