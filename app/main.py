"""Điểm khởi động của backend.

Chạy:  uvicorn app.main:app --reload
Tài liệu API tự sinh: http://127.0.0.1:8000/docs
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app import models  # noqa: F401 - import để SQLAlchemy biết các bảng
from app.core.config import settings
from app.db.session import Base, engine
from app.routers import (
    admin_applications, admin_interview, auth, candidate_applications, candidate_apply, candidate_cv_documents, candidate_detail,
    candidate_profile, candidate_recommended, candidate_saved_jobs, companies, employer_applications, employer_jobs, health, items, meta, public_jobs, users,
    nav_meta, tools, interview, candidate_cover_letters, matching, search_insights,
    salary_insights, notifications,
)

# Console Windows mặc định dùng cp1252 -> print() tiếng Việt sẽ ném UnicodeEncodeError
# và làm server KHÔNG KHỞI ĐỘNG ĐƯỢC. Ép stdout/stderr dùng UTF-8 + lỗi thay thế.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _log(message: str) -> None:
    """In log an toàn (không phụ thuộc encoding của console)."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("utf-8", "replace").decode("ascii", "replace"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tự tạo các bảng còn thiếu khi server khởi động (bảng đã có thì bỏ qua).
    # Lưu ý: create_all KHÔNG sửa bảng đã tồn tại. Đổi cột -> sửa bằng SQL hoặc xoá bảng tạo lại.
    try:
        Base.metadata.create_all(bind=engine)
        _log(f"[DB] Đã kết nối MySQL {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    except OperationalError as error:
        _log("[DB] KHÔNG kết nối được MySQL! Kiểm tra MySQL đã bật chưa và file .env.")
        if "Unknown database" in str(error.orig):
            _log("[DB] Chưa có database -> mở MySQL Workbench, chạy file sql/init.sql")
        _log(f"[DB] Chi tiết: {error.orig}")
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# CORS: cho phép trang FE (khác cổng/khác domain) gọi được API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mọi API đều bắt đầu bằng /api. Thêm router mới thì include ở đây.
app.include_router(health.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(candidate_profile.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
app.include_router(employer_jobs.router, prefix="/api")
app.include_router(employer_applications.router, prefix="/api")
# search_insights PHẢI được đăng ký TRƯỚC public_jobs:
# public_jobs có route "/jobs/{job_id}" (job_id: int) — nếu đăng ký trước, FastAPI sẽ
# khớp "relaxed" vào job_id và trả 422 thay vì gọi tới /api/jobs/relaxed.
app.include_router(search_insights.router)
app.include_router(public_jobs.router, prefix="/api")
app.include_router(candidate_applications.router, prefix="/api")
app.include_router(candidate_saved_jobs.router, prefix="/api")
app.include_router(candidate_recommended.router, prefix="/api")
app.include_router(candidate_apply.router, prefix="/api")
app.include_router(candidate_detail.router, prefix="/api")
app.include_router(nav_meta.router)
app.include_router(tools.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(admin_interview.router, prefix="/api")
app.include_router(admin_applications.router, prefix="/api")
app.include_router(candidate_cover_letters.router, prefix="/api")
app.include_router(candidate_cv_documents.router, prefix="/api")
app.include_router(matching.router)
# salary_insights dùng prefix "/salary" -> gắn thêm "/api" để ra /api/salary/insights
app.include_router(salary_insights.router, prefix="/api")
# Thông báo dùng chung (chuông thông báo trên header FE)
app.include_router(notifications.router, prefix="/api")

# Static files: uploads (avatars, documents, etc.)
UPLOADS_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(os.path.join(UPLOADS_ROOT, "avatars"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_ROOT), name="uploads")


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} đang chạy. Xem tài liệu API tại /docs"}
