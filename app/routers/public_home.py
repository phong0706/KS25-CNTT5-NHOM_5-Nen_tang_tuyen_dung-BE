"""Router công khai cho trang chủ (/api/home/*).
Tính toán từ dữ liệu thực, không trả trường nhạy cảm, không có mảng tĩnh.
Tuân thủ Bước 3 & techrecruit-rules: < 195 dòng.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.home_config_service import (
    get_public_salary_by_skill,
    get_public_featured_companies,
)

router = APIRouter(prefix="/home", tags=["Public Home"])


class SkillSalaryItem(BaseModel):
    skill: str
    median: int
    unit: str = "tr/tháng"
    sample_size: int


class HomeSalaryBySkillOut(BaseModel):
    computed_at: str
    min_sample: int
    items: List[SkillSalaryItem]
    reason: Optional[str] = None


class FeaturedCompanyItem(BaseModel):
    company_id: int
    name: str
    logo_url: Optional[str] = None
    open_jobs: int


class HomeFeaturedCompaniesOut(BaseModel):
    computed_at: str
    items: List[FeaturedCompanyItem]


@router.get("/salary-by-skill", response_model=HomeSalaryBySkillOut, summary="Lương trung vị theo kỹ năng")
def get_home_salary_by_skill(response: Response, db: Session = Depends(get_db)):
    """Trả về bảng lương trung vị theo kỹ năng tính từ tin tuyển dụng hợp lệ."""
    response.headers["Cache-Control"] = "public, max-age=60"
    data = get_public_salary_by_skill(db)
    return HomeSalaryBySkillOut(**data)


@router.get("/featured-companies", response_model=HomeFeaturedCompaniesOut, summary="Doanh nghiệp đang tuyển dụng")
def get_home_featured_companies(response: Response, db: Session = Depends(get_db)):
    """Trả về danh sách doanh nghiệp đã xác minh đang tuyển dụng."""
    response.headers["Cache-Control"] = "public, max-age=60"
    data = get_public_featured_companies(db)
    return HomeFeaturedCompaniesOut(**data)
