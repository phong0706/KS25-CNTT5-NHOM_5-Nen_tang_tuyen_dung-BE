"""API CRUD cho danh mục Ngành nghề (Industries).

Endpoints:
    GET    /api/industries          Danh sách (dropdown: ?status=active)
    GET    /api/industries/{id}     Chi tiết
    POST   /api/industries          Thêm mới
    PUT    /api/industries/{id}     Cập nhật
    DELETE /api/industries/{id}     Ẩn (soft delete)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import catalog as catalog_crud
from app.db.session import get_db
from app.schemas.catalog_schema import CatalogCreate, CatalogUpdate, CatalogResponse

router = APIRouter(prefix="/industries", tags=["Industries"])


def get_industry_or_404(industry_id: int, db: Session = Depends(get_db)):
    """Helper: Lấy industry hoặc trả lỗi 404."""
    industry = catalog_crud.get_industry(db, industry_id)
    if industry is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy ngành nghề id={industry_id}")
    return industry


@router.get("", response_model=list[CatalogResponse])
def list_industries(status: str | None = "active", db: Session = Depends(get_db)):
    """
    Lấy danh sách ngành nghề.
    
    - status=active: chỉ lấy ngành đang hoạt động (mặc định, dùng cho dropdown)
    - status=inactive: chỉ lấy ngành đã ẩn
    - status=None: lấy tất cả
    """
    return catalog_crud.get_industries(db, status=status)


@router.get("/{industry_id}", response_model=CatalogResponse)
def get_industry(industry=Depends(get_industry_or_404)):
    """Lấy chi tiết 1 ngành nghề."""
    return industry


@router.post("", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
def create_industry(data: CatalogCreate, db: Session = Depends(get_db)):
    """Tạo ngành nghề mới. Tên phải duy nhất."""
    try:
        return catalog_crud.create_industry(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{industry_id}", response_model=CatalogResponse)
def update_industry(
    data: CatalogUpdate,
    industry=Depends(get_industry_or_404),
    db: Session = Depends(get_db)
):
    """Cập nhật ngành nghề. Tên mới không được trùng với ngành khác."""
    try:
        return catalog_crud.update_industry(db, industry, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{industry_id}", response_model=CatalogResponse)
def delete_industry(
    industry=Depends(get_industry_or_404),
    db: Session = Depends(get_db)
):
    """
    Ẩn ngành nghề (soft delete: đổi status='inactive').
    Không xóa nếu đang được sử dụng trong jobs, companies...
    """
    try:
        return catalog_crud.delete_industry(db, industry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
