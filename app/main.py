"""Điểm khởi động của backend.

Chạy: uvicorn app.main:app --reload
Tài liệu API: http://127.0.0.1:8000/docs
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app import models  # noqa: F401
from app.core.config import settings
from app.db.session import Base, engine
from app.routers import (
    admin_applications,
    admin_audit_and_cvs,
    admin_companies_cvs,
    admin_company_logos,
    admin_interview,
    admin_jobs,
    admin_verifications,
    applications,
    auth,
    candidate_applications,
    candidate_apply,
    candidate_cover_letters,
    candidate_cv_documents,
    candidate_cvs,
    candidate_detail,
    candidate_followed_companies,
    candidate_job_matches,
    candidate_profile,
    candidate_recommended,
    candidate_saved_jobs,
    career_path,
    companies,
    company,
    company_logos,
    cv,
    employer_applications,
    employer_interviews,
    employer_job_moderation,
    employer_jobs,
    employer_verification,
    health,
    industries,
    interview,
    items,
    jobs,
    locations,
    matching,
    meta,
    nav_meta,
    notifications,
    public_jobs,
    reports,
    salary_insights,
    search_insights,
    skills,
    statistics,
    tools,
    users,
    public_home,
    admin_home_salary,
    admin_home_companies,
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


# Đảm bảo thư mục upload tồn tại trước khi mount StaticFiles
upload_dir_path = Path(settings.UPLOAD_DIR)
upload_dir_path.mkdir(parents=True, exist_ok=True)
(upload_dir_path / "avatars").mkdir(parents=True, exist_ok=True)
(upload_dir_path / "logos").mkdir(parents=True, exist_ok=True)

cv_upload_dir_str = getattr(settings, "CV_UPLOAD_DIR", None)
if cv_upload_dir_str:
    Path(cv_upload_dir_str).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        _log(f"[DB] Đã kết nối MySQL {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    except OperationalError as error:
        _log("[DB] KHÔNG kết nối được MySQL! Kiểm tra MySQL đã bật chưa và file .env.")
        if "Unknown database" in str(error.orig):
            _log("[DB] Chưa có database -> mở MySQL Workbench, chạy file sql/init.sql")
        _log(f"[DB] Chi tiết: {error.orig}")

    _log(f"[Upload] Thư mục lưu ảnh/CV: {upload_dir_path.resolve()}")
    if cv_upload_dir_str:
        _log(f"[CV Upload] Thư mục lưu CV: {Path(cv_upload_dir_str).resolve()}")

    yield

    try:
        from app.realtime.manager import manager
        await manager.close_all_shutdown()
    except Exception:
        pass


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=("*" not in _cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Đăng ký router phục vụ ảnh logo có header bảo mật nosniff trước khi mount StaticFiles
app.include_router(company_logos.router)

# Phục vụ file tĩnh ở cả /static và /uploads (khớp với đường dẫn trả về của company.py & avatars)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Đăng ký toàn bộ router
app.include_router(health.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(company.router, prefix="/api")
app.include_router(company.admin_router, prefix="/api")
app.include_router(candidate_profile.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
app.include_router(industries.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(employer_job_moderation.router, prefix="/api")
app.include_router(employer_jobs.router, prefix="/api")
app.include_router(employer_applications.router, prefix="/api")
app.include_router(employer_interviews.router, prefix="/api")
app.include_router(employer_verification.router, prefix="/api")

# search_insights PHẢI được đăng ký TRƯỚC public_jobs và jobs:
# public_jobs / jobs có route "/jobs/{job_id}" (job_id: int) — nếu đăng ký trước, FastAPI sẽ
# khớp "relaxed" vào job_id và trả 422 thay vì gọi tới /api/jobs/relaxed.
app.include_router(search_insights.router)
app.include_router(public_jobs.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")

app.include_router(applications.router, prefix="/api")
app.include_router(candidate_applications.router, prefix="/api")
app.include_router(candidate_cvs.router, prefix="/api")
app.include_router(candidate_saved_jobs.router, prefix="/api")
app.include_router(candidate_followed_companies.router, prefix="/api")
app.include_router(candidate_recommended.router, prefix="/api")
app.include_router(candidate_job_matches.router, prefix="/api")
app.include_router(candidate_apply.router, prefix="/api")
app.include_router(candidate_detail.router, prefix="/api")
app.include_router(nav_meta.router)
app.include_router(tools.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(admin_interview.router, prefix="/api")
app.include_router(admin_applications.router, prefix="/api")
app.include_router(admin_companies_cvs.router, prefix="/api")
app.include_router(admin_audit_and_cvs.router, prefix="/api")
app.include_router(admin_verifications.router, prefix="/api")
app.include_router(admin_jobs.router, prefix="/api")
app.include_router(admin_company_logos.router, prefix="/api")
app.include_router(candidate_cover_letters.router, prefix="/api")
app.include_router(candidate_cv_documents.router, prefix="/api")
app.include_router(matching.router)
# salary_insights dùng prefix "/salary" -> gắn thêm "/api" để ra /api/salary/insights
app.include_router(salary_insights.router, prefix="/api")
# Thông báo dùng chung (chuông thông báo trên header FE)
app.include_router(notifications.router, prefix="/api")
app.include_router(career_path.router, prefix="/api")
app.include_router(career_path.router)
app.include_router(public_home.router, prefix="/api")
app.include_router(admin_home_salary.router, prefix="/api")
app.include_router(admin_home_companies.router, prefix="/api")
# Báo cáo vi phạm
app.include_router(reports.router, prefix="/api")
# Thống kê Dashboard
app.include_router(statistics.router, prefix="/api")
# WebSocket & Realtime tickets
from app.realtime.router import router as realtime_router
app.include_router(realtime_router)


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} is running. API docs at /docs"}