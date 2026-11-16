"""Kiểm thử hồi quy cho các bản sửa lỗi QA.

Bao gồm:
  - Chuẩn hoá mức lương USD/VND (ngưỡng cũ 10.000 làm mức lương VND bị nhân nhầm).
  - Đăng ký route: /api/jobs/relaxed phải được khớp TRƯỚC /api/jobs/{job_id}.
  - Model SavedSearch tạo đúng bảng `saved_searches`.
"""
import pytest

from app.main import app
from app.models.application import SavedSearch
from app.routers.salary_insights import USD_THRESHOLD, _normalize_val


# ------------------------------------------------------------------
# 1. Chuẩn hoá mức lương
# ------------------------------------------------------------------

def test_normalize_val_keeps_vnd_untouched():
    """Mức lương VND phải giữ nguyên, không bị nhân tỷ giá USD."""
    assert _normalize_val(25_000_000) == 25_000_000
    assert _normalize_val(3_000_000) == 3_000_000
    assert _normalize_val(50_000_000) == 50_000_000


def test_normalize_val_converts_usd():
    """Mức lương khai báo bằng USD (số nhỏ) được quy đổi sang VNĐ."""
    assert _normalize_val(1000) == 1000 * 25400
    assert _normalize_val(500) == 500 * 25400


def test_normalize_val_edge_cases():
    assert _normalize_val(None) is None
    assert _normalize_val(0) is None
    assert _normalize_val(-100) is None


def test_usd_threshold_is_safe_for_it_salaries():
    """Ngưỡng USD phải nằm dưới mức lương IT tối thiểu (3.000.000 VND)."""
    assert USD_THRESHOLD < 3_000_000
    assert USD_THRESHOLD >= 10_000  # vẫn bắt được các mức USD thực tế


# ------------------------------------------------------------------
# 2. Thứ tự đăng ký route
# ------------------------------------------------------------------

def _route_paths():
    return [getattr(r, "path", "") for r in app.routes]


def test_jobs_relaxed_route_exists():
    assert "/api/jobs/relaxed" in _route_paths()


def test_jobs_relaxed_registered_before_jobs_by_id():
    """Route có tham số phải đứng SAU route tĩnh, nếu không FastAPI sẽ khớp sai.

    Đây là lỗi đã gặp: /api/jobs/relaxed bị route /api/jobs/{job_id} "nuốt" và
    trả 422 (int_parsing) thay vì gọi tới handler đúng.
    """
    paths = _route_paths()
    idx_relaxed = paths.index("/api/jobs/relaxed")
    idx_by_id = paths.index("/api/jobs/{job_id}")
    assert idx_relaxed < idx_by_id, (
        "/api/jobs/relaxed phải được đăng ký trước /api/jobs/{job_id}"
    )


def test_salary_insights_route_path():
    assert "/api/salary/insights" in _route_paths()


# ------------------------------------------------------------------
# 3. Model SavedSearch
# ------------------------------------------------------------------

def test_saved_search_model_table_and_columns():
    assert SavedSearch.__tablename__ == "saved_searches"
    cols = set(SavedSearch.__table__.columns.keys())
    assert {"user_id", "name", "filters_json"} <= cols
