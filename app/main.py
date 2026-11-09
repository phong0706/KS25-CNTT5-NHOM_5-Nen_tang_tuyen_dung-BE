"""Điểm khởi động của backend.

Chạy: uvicorn app.main:app --reload
Tài liệu API: http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app import models
from app.core.config import settings
from app.db.session import Base, engine
from app.routers import health, items, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        print(f"[DB] Đã kết nối MySQL {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    except OperationalError as error:
        print("[DB] KHÔNG kết nối được MySQL! Kiểm tra MySQL và file .env.")
        if "Unknown database" in str(error.orig):
            print("[DB] Chưa có database -> chạy file sql/init.sql")
        print(f"[DB] Chi tiết: {error.orig}")
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} đang chạy. Xem tài liệu API tại /docs"}