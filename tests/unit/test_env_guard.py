"""
backend/tests/unit/test_env_guard.py
Kiểm thử cơ chế tự động bảo vệ DB test (BUG-S2-07).
Khi chạy trong ngữ cảnh kiểm thử, DB_NAME phải tự động là app_db_test để không làm bẩn app_db.
"""
import sys
from app.core.config import settings

def test_test_environment_uses_test_db():
    assert "test" in settings.DB_NAME, f"DB_NAME '{settings.DB_NAME}' must contain 'test' during test runs!"
