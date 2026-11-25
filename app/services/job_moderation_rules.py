"""Quy tắc chuyển trạng thái và thẩm định nghiệp vụ duyệt tin tuyển dụng.

Module thuần túy (pure logic), không phụ thuộc database, dễ kiểm thử đơn vị.
"""
from datetime import date
from typing import Any

from fastapi import HTTPException, status


# Bảng chuyển trạng thái được phép theo vai trò người thực hiện
ALLOWED_TRANSITIONS: dict[str, dict[str, list[str]]] = {
    "employer": {
        "draft": ["pending"],
        "pending": ["draft"],
        "rejected": ["pending"],
        "published": ["closed"],
        "open": ["closed"],
        "closed": ["pending"],
    },
    "admin": {
        "pending": ["published", "open", "rejected", "deleted"],
        "published": ["closed", "deleted"],
        "open": ["closed", "deleted"],
    },
}

VALID_STATUSES = {"draft", "pending", "published", "open", "rejected", "closed", "deleted"}


def validate_job_transition(current_status: str, target_status: str, role: str) -> None:
    """Xác thực tính hợp lệ của việc chuyển đổi trạng thái tin tuyển dụng."""
    if role not in ALLOWED_TRANSITIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vai trò không có quyền thực hiện chuyển trạng thái tin tuyển dụng.",
        )

    if current_status not in VALID_STATUSES or target_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="INVALID_TRANSITION",
        )

    allowed_targets = ALLOWED_TRANSITIONS[role].get(current_status, [])
    if target_status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="INVALID_TRANSITION",
        )


def validate_rejection_reason(reason: Any) -> str:
    """Xác thực lý do từ chối tin tuyển dụng: >= 10 ký tự, tối đa 1000 ký tự."""
    if not isinstance(reason, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lý do từ chối phải là chuỗi văn bản.",
        )

    cleaned = reason.strip()
    if len(cleaned) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lý do từ chối phải có ít nhất 10 ký tự.",
        )

    if len(cleaned) > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lý do từ chối không được vượt quá 1000 ký tự.",
        )

    return cleaned


def validate_optimistic_version(expected_version: Any, current_version: int) -> None:
    """Kiểm tra xung đột phiên bản (Optimistic Locking)."""
    if expected_version is None or not isinstance(expected_version, int) or expected_version <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phiên bản (version) phải là số nguyên dương hợp lệ.",
        )

    if expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VERSION_CONFLICT",
        )


def is_job_public(
    status_val: str,
    deadline: date | None,
    company_verified: bool,
    now_date: date,
    deleted_at: Any = None,
) -> bool:
    """Kiểm tra tin tuyển dụng có đủ điều kiện hiển thị công khai hay không.
    
    Điều kiện:
    1. Trạng thái là 'open' hoặc 'published'
    2. Chưa bị xóa mềm (deleted_at is None)
    3. Công ty đã xác minh (company_verified == True)
    4. Chưa hết hạn ứng tuyển (deadline is None hoặc deadline >= now_date)
    """
    if deleted_at is not None:
        return False

    if status_val not in ("open", "published"):
        return False

    if not company_verified:
        return False

    if deadline is not None and deadline < now_date:
        return False

    return True
