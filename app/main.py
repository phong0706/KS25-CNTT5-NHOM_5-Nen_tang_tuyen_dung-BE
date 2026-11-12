"""Điểm khởi động của backend.

Chạy: uvicorn app.main:app --reload
Tài liệu API: http://127.0.0.1:8000/docs
"""
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
    applications,
    auth,
    candidate_profile,
    company,
    cv,
    health,
    industries,
    items,
    jobs,
    locations,
    skills,
)

# Fix encoding cho Windows console (tránh lỗi UnicodeEncodeError với tiếng Việt)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Đảm bảo thư mục upload tồn tại trước khi mount StaticFiles
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CV_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        print(
            f"[DB] Ket noi MySQL thanh cong {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        )
    except OperationalError as error:
        print("[DB] KHONG ket noi duoc MySQL! Kiem tra MySQL va file .env.")
        if "Unknown database" in str(error.orig):
            print("[DB] Chua co database -> chay file sql/init.sql")
        print(f"[DB] Chi tiet: {error.orig}")

    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    print(f"[Upload] Thu muc luu anh/CV: {upload_path.resolve()}")

    cv_upload_path = Path(settings.CV_UPLOAD_DIR)
    cv_upload_path.mkdir(parents=True, exist_ok=True)
    print(f"[CV Upload] Thu muc luu CV: {cv_upload_path.resolve()}")

    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phục vụ file tĩnh ở cả /static và /uploads (khớp với đường dẫn trả về của company.py)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Đăng ký toàn bộ router
app.include_router(health.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(company.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(candidate_profile.router, prefix="/api")
app.include_router(industries.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(skills.router, prefix="/api")


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} is running. API docs at /docs"}