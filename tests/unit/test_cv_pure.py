"""Unit test thuần: nghiệp vụ xóa mềm, chọn CV mặc định và kiểm tra file upload.
Tuân thủ techrecruit-rules: < 200 dòng, không mock phức tạp, test thuần.
"""
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from app.services.cv_service import (
    pick_new_default_cv,
    should_delete_physical_file,
    validate_cv_content,
)


def test_should_delete_physical_file():
    # CV chưa dùng trong đơn nào và không có CV nào khác trỏ cùng file -> xóa file vật lý
    assert should_delete_physical_file(used_in_apps_count=0, other_cv_references_count=0) is True

    # CV đang dùng trong ít nhất 1 đơn -> giữ lại file vật lý
    assert should_delete_physical_file(used_in_apps_count=1, other_cv_references_count=0) is False
    assert should_delete_physical_file(used_in_apps_count=5, other_cv_references_count=0) is False

    # CV có bản ghi khác cùng tham chiếu stored_name -> giữ lại file vật lý
    assert should_delete_physical_file(used_in_apps_count=0, other_cv_references_count=1) is False


def test_pick_new_default_cv():
    class DummyCV:
        def __init__(self, id, created_at, is_default=False):
            self.id = id
            self.created_at = created_at
            self.is_default = is_default

    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 3, tzinfo=timezone.utc)

    cv1 = DummyCV(1, t1)
    cv2 = DummyCV(2, t2)
    cv3 = DummyCV(3, t3)

    # Danh sách còn lại rỗng -> None
    assert pick_new_default_cv([]) is None

    # Danh sách có phần tử -> chọn phần tử mới nhất (t3)
    picked = pick_new_default_cv([cv1, cv3, cv2])
    assert picked.id == 3

    # Danh sách 1 phần tử -> chọn chính nó
    picked_single = pick_new_default_cv([cv1])
    assert picked_single.id == 1


def test_validate_cv_content_zero_byte():
    with pytest.raises(HTTPException) as exc_info:
        validate_cv_content(b"")
    assert exc_info.value.status_code == 422
    assert "0 byte" in exc_info.value.detail.lower()


def test_validate_cv_content_under_1kb():
    # File hợp lệ định dạng PDF nhưng < 1024 bytes (ví dụ 200 bytes)
    mini_pdf = b"%PDF-1.4\n" + b"A" * 200 + b"\n%%EOF"
    assert len(mini_pdf) < 1024

    with pytest.raises(HTTPException) as exc_info:
        validate_cv_content(mini_pdf)
    assert exc_info.value.status_code == 422
    assert "1 kb" in exc_info.value.detail.lower()


def test_validate_cv_content_valid_sizes():
    # 1.5 KB valid PDF
    valid_pdf = b"%PDF-1.4\n" + b"X" * 1500 + b"\n%%EOF"
    mime, ext = validate_cv_content(valid_pdf)
    assert mime == "application/pdf"
    assert ext == ".pdf"


def test_validate_cv_content_exceed_max_size():
    huge_pdf = b"%PDF-1.4\n" + b"X" * (5 * 1024 * 1024 + 10)
    with pytest.raises(HTTPException) as exc_info:
        validate_cv_content(huge_pdf)
    assert exc_info.value.status_code == 422
    assert "5 mb" in exc_info.value.detail.lower()


def test_validate_cv_content_fake_extension():
    fake_content = b"This is just a plain text file masquerading as a document." * 30
    assert len(fake_content) > 1024
    with pytest.raises(HTTPException) as exc_info:
        validate_cv_content(fake_content)
    assert exc_info.value.status_code == 422
    assert "không hợp lệ" in exc_info.value.detail.lower()

