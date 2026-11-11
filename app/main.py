"""Diem khoi dong cua backend.
 
Chay: uvicorn app.main:app --reload
Tai lieu API: http://127.0.0.1:8000/docs
"""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app import models  # noqa: F401
from app.core.config import settings
from app.db.session import Base, engine
from app.routers import auth, candidate_profile, cv, health, items, jobs

# Fix encoding cho Windows console (tranh loi UnicodeEncodeError voi tieng Viet)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        print(f"[DB] Ket noi MySQL thanh cong {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    except OperationalError as error:
        print("[DB] KHONG ket noi duoc MySQL! Kiem tra MySQL va file .env.")
        if "Unknown database" in str(error.orig):
            print("[DB] Chua co database -> chay file sql/init.sql")
        print(f"[DB] Chi tiet: {error.orig}")
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
app.include_router(auth.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(candidate_profile.router, prefix="/api")


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} is running. API docs at /docs"}