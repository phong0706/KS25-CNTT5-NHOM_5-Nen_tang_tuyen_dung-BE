"""Unit tests cho bảng chuyển trạng thái và quy tắc nghiệp vụ duyệt tin (Lớp A)."""
from datetime import date, datetime, timezone
import pytest
from fastapi import HTTPException

from app.services.job_moderation_rules import (
    ALLOWED_TRANSITIONS,
    is_job_public,
    validate_job_transition,
    validate_optimistic_version,
    validate_rejection_reason,
)


def test_transition_allowed_employer_draft_to_pending():
    """Employer gửi duyệt tin từ draft -> pending."""
    validate_job_transition("draft", "pending", "employer")


def test_transition_allowed_employer_pending_to_draft():
    """Employer rút tin từ pending về draft."""
    validate_job_transition("pending", "draft", "employer")


def test_transition_allowed_admin_pending_to_published():
    """Admin duyệt tin từ pending -> published."""
    validate_job_transition("pending", "published", "admin")


def test_transition_allowed_admin_pending_to_rejected():
    """Admin từ chối tin từ pending -> rejected."""
    validate_job_transition("pending", "rejected", "admin")


def test_transition_allowed_employer_rejected_to_pending():
    """Employer nộp lại tin từ rejected -> pending."""
    validate_job_transition("rejected", "pending", "employer")


def test_transition_allowed_published_to_closed():
    """Đóng tin từ published -> closed (cả admin và employer)."""
    validate_job_transition("published", "closed", "employer")
    validate_job_transition("published", "closed", "admin")


def test_transition_allowed_closed_to_pending():
    """Employer nộp duyệt lại tin đã đóng: closed -> pending."""
    validate_job_transition("closed", "pending", "employer")


def test_transition_disallowed_draft_to_published():
    """Employer không thể tự chuyển draft -> published."""
    with pytest.raises(HTTPException) as exc:
        validate_job_transition("draft", "published", "employer")
    assert exc.value.status_code == 409
    assert exc.value.detail == "INVALID_TRANSITION"


def test_transition_disallowed_rejected_to_published():
    """Admin không thể duyệt thẳng tin rejected sang published mà không qua pending."""
    with pytest.raises(HTTPException) as exc:
        validate_job_transition("rejected", "published", "admin")
    assert exc.value.status_code == 409
    assert exc.value.detail == "INVALID_TRANSITION"


def test_transition_disallowed_closed_to_published():
    """Không thể mở trực tiếp closed -> published."""
    with pytest.raises(HTTPException) as exc:
        validate_job_transition("closed", "published", "employer")
    assert exc.value.status_code == 409


def test_transition_invalid_role_or_nonexistent_status():
    """Vai trò hoặc trạng thái không hợp lệ bị từ chối."""
    with pytest.raises(HTTPException) as exc:
        validate_job_transition("draft", "pending", "candidate")
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        validate_job_transition("unknown_status", "pending", "employer")
    assert exc2.value.status_code == 409


def test_rejection_reason_empty_or_whitespace():
    """Lý do từ chối rỗng hoặc chỉ khoảng trắng bị từ chối với 422."""
    for bad_reason in [None, "", "   ", "\t\n  "]:
        with pytest.raises(HTTPException) as exc:
            validate_rejection_reason(bad_reason)
        assert exc.value.status_code == 422


def test_rejection_reason_length_validation():
    """Lý do từ chối dưới 10 ký tự -> 422; đúng 10 ký tự -> chấp nhận."""
    with pytest.raises(HTTPException) as exc:
        validate_rejection_reason("Ngắn quá")
    assert exc.value.status_code == 422

    exact_10 = validate_rejection_reason("1234567890")
    assert exact_10 == "1234567890"


def test_rejection_reason_unicode_vietnamese():
    """Lý do tiếng Việt có dấu được chấp nhận và giữ nguyên vẹn."""
    reason = "Mô tả công việc chưa nêu rõ mức lương và quyền lợi bảo hiểm."
    result = validate_rejection_reason(f"  {reason}  ")
    assert result == reason


def test_rejection_reason_exceeds_max_length():
    """Lý do quá 1000 ký tự bị từ chối với 422."""
    too_long = "a" * 1001
    with pytest.raises(HTTPException) as exc:
        validate_rejection_reason(too_long)
    assert exc.value.status_code == 422


def test_validate_optimistic_version():
    """Cùng version -> pass; khác version -> 409; version âm/thiếu -> 422."""
    # Khớp version
    validate_optimistic_version(1, 1)
    validate_optimistic_version(5, 5)

    # Lệch version -> 409
    with pytest.raises(HTTPException) as exc:
        validate_optimistic_version(expected_version=1, current_version=2)
    assert exc.value.status_code == 409
    assert exc.value.detail == "VERSION_CONFLICT"

    # Version âm hoặc không hợp lệ -> 422
    for bad in [-1, 0, None]:
        with pytest.raises(HTTPException) as exc2:
            validate_optimistic_version(expected_version=bad, current_version=1)
        assert exc2.value.status_code == 422


def test_is_job_public_combinations():
    """Tổ hợp trạng thái x hạn nộp x xác minh công ty."""
    now_date = date(2026, 11, 18)

    # Đạt mọi điều kiện
    assert is_job_public("published", date(2026, 11, 25), True, now_date) is True
    # Hạn là không giới hạn (None) -> Vẫn công khai
    assert is_job_public("published", None, True, now_date) is True

    # Ranh giới hạn nộp
    # Hôm nay: vẫn còn hạn
    assert is_job_public("published", date(2026, 11, 18), True, now_date) is True
    # Hôm qua: đã hết hạn
    assert is_job_public("published", date(2026, 11, 17), True, now_date) is False

    # Công ty chưa xác minh -> Không công khai
    assert is_job_public("published", date(2026, 11, 25), False, now_date) is False

    # Các trạng thái khác published -> Không công khai
    for st in ["draft", "pending", "rejected", "closed", "hidden"]:
        assert is_job_public(st, date(2026, 11, 25), True, now_date) is False
