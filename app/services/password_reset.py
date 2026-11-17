"""Dịch vụ xử lý quên mật khẩu và đặt lại mật khẩu an toàn."""
import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User

logger = logging.getLogger("app.services.password_reset")


def _hash_token(code: str) -> str:
    """Hash SHA-256 mã xác nhận trước khi lưu/so khớp với DB."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _generate_code() -> str:
    """Tạo mã xác nhận 6 số ngẫu nhiên an toàn bằng secrets."""
    return f"{secrets.randbelow(900000) + 100000:06d}"


def _send_reset_email(email: str, code: str) -> None:
    """Gửi mã đặt lại mật khẩu qua email, fallback ghi log ở môi trường dev."""
    if settings.SMTP_HOST and settings.SMTP_USER:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{settings.APP_NAME}] Mã xác nhận đặt lại mật khẩu"
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = email
            body = (
                f"<p>Xin chào,</p><p>Mã xác nhận TechRecruit: <b>{code}</b> "
                f"(hạn {settings.RESET_CODE_EXPIRE_MINUTES} phút).</p>"
            )
            msg.attach(MIMEText(body, "html", "utf-8"))
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as s:
                s.starttls()
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Không thể gửi email qua SMTP: %s", exc)

    if settings.ENVIRONMENT != "production" and settings.LOG_RESET_CODE_IN_DEV:
        logger.info("[DEV ONLY] Mã đặt lại mật khẩu cho %s: %s", email, code)


def request_password_reset(
    db: Session,
    email: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Tạo mã đặt lại mật khẩu (chống lộ danh sách tài khoản)."""
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    generic_msg = (
        "Nếu email của bạn tồn tại trong hệ thống, chúng tôi đã gửi mã đặt lại mật khẩu. "
        "Vui lòng kiểm tra hộp thư."
    )

    if not user:
        return {"message": generic_msg, "cooldown_seconds": settings.RESET_CODE_COOLDOWN_SECONDS}

    now = datetime.now()
    recent = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if recent and recent.created_at:
        diff = (now - recent.created_at).total_seconds()
        if -10 < diff < settings.RESET_CODE_COOLDOWN_SECONDS:
            left = max(1, int(settings.RESET_CODE_COOLDOWN_SECONDS - max(0, diff)))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMITED",
                    "message": f"Vui lòng đợi {left} giây trước khi yêu cầu mã mới.",
                },
            )

    code = _generate_code()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(code),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.RESET_CODE_EXPIRE_MINUTES),
        ip_address=ip_address,
        user_agent=user_agent[:255] if user_agent else None,
    )
    db.add(token)
    db.commit()

    _send_reset_email(clean_email, code)
    return {"message": generic_msg, "cooldown_seconds": settings.RESET_CODE_COOLDOWN_SECONDS}


def reset_password_with_code(
    db: Session, email: str, code: str, new_password: str
) -> dict:
    """Xác nhận mã và đặt lại mật khẩu mới, hủy toàn bộ phiên cũ."""
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WEAK_PASSWORD", "message": "Mật khẩu mới phải có ít nhất 6 ký tự."},
        )

    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CODE", "message": "Mã xác nhận hoặc email không hợp lệ."},
        )

    token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id, PasswordResetToken.is_used == False)  # noqa: E712
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CODE",
                "message": "Không tìm thấy yêu cầu đặt lại mật khẩu hoặc mã đã được dùng.",
            },
        )

    now = datetime.now()
    if token.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CODE_EXPIRED",
                "message": "Mã xác nhận đã hết hạn (quá 15 phút). Vui lòng yêu cầu mã mới.",
            },
        )

    if token.attempts >= settings.RESET_CODE_MAX_ATTEMPTS:
        token.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TOO_MANY_ATTEMPTS",
                "message": "Bạn đã nhập sai mã quá số lần cho phép. Vui lòng yêu cầu mã mới.",
            },
        )

    if token.token_hash != _hash_token(code):
        token.attempts += 1
        rem = settings.RESET_CODE_MAX_ATTEMPTS - token.attempts
        if rem <= 0:
            token.is_used = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "TOO_MANY_ATTEMPTS",
                    "message": "Bạn đã nhập sai mã quá số lần cho phép. Vui lòng yêu cầu mã mới.",
                },
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CODE",
                "message": f"Mã xác nhận không chính xác. Bạn còn {rem} lần thử.",
            },
        )

    # Đánh dấu đã dùng và cập nhật mật khẩu, tăng token_version để hủy tất cả phiên đăng nhập
    token.is_used = True
    token.used_at = now
    user.password = hash_password(new_password)
    user.token_version = getattr(user, "token_version", 1) + 1
    db.commit()

    return {"message": "Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới."}
