"""API CRUD cho danh mục Địa điểm (Locations).

Endpoints:
    GET    /api/locations          Danh sách (dropdown: ?status=active)
    GET    /api/locations/{id}     Chi tiết
    POST   /api/locations          Thêm mới
    PUT    /api/locations/{id}     Cập nhật
    DELETE /api/locations/{id}     Ẩn (soft delete)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import catalog as catalog_crud
from app.db.session import get_db
from app.schemas.catalog_schema import CatalogCreate, CatalogUpdate, CatalogResponse

router = APIRouter(prefix="/locations", tags=["Locations"])


def get_location_or_404(location_id: int, db: Session = Depends(get_db)):
    """Helper: Lấy location hoặc trả lỗi 404."""
    location = catalog_crud.get_location(db, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy địa điểm id={location_id}")
    return location


@router.get("", response_model=list[CatalogResponse])
def list_locations(status: str | None = "active", db: Session = Depends(get_db)):
    """
    Lấy danh sách địa điểm.
    
    - status=active: chỉ lấy địa điểm đang hoạt động (mặc định, dùng cho dropdown)
    - status=inactive: chỉ lấy địa điểm đã ẩn
    - status=None: lấy tất cả
    """
    return catalog_crud.get_locations(db, status=status)


@router.get("/{location_id}", response_model=CatalogResponse)
def get_location(location=Depends(get_location_or_404)):
    """Lấy chi tiết 1 địa điểm."""
    return location


@router.post("", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
def create_location(data: CatalogCreate, db: Session = Depends(get_db)):
    """Tạo địa điểm mới. Tên phải duy nhất."""
    try:
        return catalog_crud.create_location(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{location_id}", response_model=CatalogResponse)
def update_location(
    data: CatalogUpdate,
    location=Depends(get_location_or_404),
    db: Session = Depends(get_db)
):
    """Cập nhật địa điểm. Tên mới không được trùng với địa điểm khác."""
    try:
        return catalog_crud.update_location(db, location, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{location_id}", response_model=CatalogResponse)
def delete_location(
    location=Depends(get_location_or_404),
    db: Session = Depends(get_db)
):
    """
    Ẩn địa điểm (soft delete: đổi status='inactive').
    Không xóa nếu đang được sử dụng trong jobs, companies...
    """
    try:
        return catalog_crud.delete_location(db, location)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
