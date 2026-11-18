"""Unit & Integration tests cho luồng Xác minh công ty (Bước 2 -> Bước 5 & Bước 8)."""
from pathlib import Path
import sys
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.company_verification_rules import (
    normalize_and_validate_mst,
    validate_license_file_bytes,
    validate_reason_text,
)


def test_mst_normalization_and_validation():
    assert normalize_and_validate_mst(" 010 124 8141 ") == "0101248141"
    assert normalize_and_validate_mst("0101-248-141") == "0101248141"
    assert normalize_and_validate_mst("0101248141 - 001") == "0101248141-001"
    assert normalize_and_validate_mst("0101248141001") == "0101248141-001"

    for bad in ["", "12345", "010124814A", "0101248141-12", "01012-48141001", "0101248141-0012"]:
        with pytest.raises(HTTPException) as exc:
            normalize_and_validate_mst(bad)
        assert exc.value.status_code == 422
        assert exc.value.detail["field"] == "mst"


def test_license_magic_bytes_rejects_exe_renamed_to_png():
    # .exe file (MZ header) renamed to .png -> must be rejected
    fake_png_exe = b"MZ\x90\x00\x03\x00\x00\x00fake-executable-bytes"
    with pytest.raises(HTTPException) as exc:
        validate_license_file_bytes(fake_png_exe)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "INVALID_LICENSE_FILE"

    # Valid PNG, JPG, PDF magic bytes pass
    assert validate_license_file_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") == ("image/png", ".png")
    assert validate_license_file_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF") == ("image/jpeg", ".jpg")
    assert validate_license_file_bytes(b"%PDF-1.7\n1 0 obj") == ("application/pdf", ".pdf")


def test_reason_validation_requires_minimum_10_chars():
    for short in [None, "", "   ", "mờ quá", "123456789"]:
        with pytest.raises(HTTPException) as exc:
            validate_reason_text(short)
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "REASON_TOO_SHORT"

    assert validate_reason_text("  Ảnh giấy phép bị mờ không đọc được MST  ") == "Ảnh giấy phép bị mờ không đọc được MST"
