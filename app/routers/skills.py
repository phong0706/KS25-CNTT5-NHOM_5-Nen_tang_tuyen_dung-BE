"""API CRUD cho danh mục Kỹ năng (Skills).

Endpoints:
    GET    /api/skills          Danh sách (dropdown: ?status=active)
    GET    /api/skills/{id}     Chi tiết
    POST   /api/skills          Thêm mới
    PUT    /api/skills/{id}     Cập nhật
    DELETE /api/skills/{id}     Ẩn (soft delete)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import catalog as catalog_crud
from app.db.session import get_db
from app.schemas.catalog_schema import CatalogCreate, CatalogUpdate, CatalogResponse

router = APIRouter(prefix="/skills", tags=["Skills"])


def get_skill_or_404(skill_id: int, db: Session = Depends(get_db)):
    """Helper: Lấy skill hoặc trả lỗi 404."""
    skill = catalog_crud.get_skill(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kỹ năng id={skill_id}")
    return skill


@router.get("", response_model=list[CatalogResponse])
def list_skills(status: str | None = "active", db: Session = Depends(get_db)):
    """
    Lấy danh sách kỹ năng.
    
    - status=active: chỉ lấy kỹ năng đang hoạt động (mặc định, dùng cho dropdown)
    - status=inactive: chỉ lấy kỹ năng đã ẩn
    - status=None: lấy tất cả
    """
    return catalog_crud.get_skills(db, status=status)


@router.get("/{skill_id}", response_model=CatalogResponse)
def get_skill(skill=Depends(get_skill_or_404)):
    """Lấy chi tiết 1 kỹ năng."""
    return skill


@router.post("", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
def create_skill(data: CatalogCreate, db: Session = Depends(get_db)):
    """Tạo kỹ năng mới. Tên phải duy nhất."""
    try:
        return catalog_crud.create_skill(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{skill_id}", response_model=CatalogResponse)
def update_skill(
    data: CatalogUpdate,
    skill=Depends(get_skill_or_404),
    db: Session = Depends(get_db)
):
    """Cập nhật kỹ năng. Tên mới không được trùng với kỹ năng khác."""
    try:
        return catalog_crud.update_skill(db, skill, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{skill_id}", response_model=CatalogResponse)
def delete_skill(
    skill=Depends(get_skill_or_404),
    db: Session = Depends(get_db)
):
    """
    Ẩn kỹ năng (soft delete: đổi status='inactive').
    Không xóa nếu đang được sử dụng trong user_skills, job_skills...
    """
    try:
        return catalog_crud.delete_skill(db, skill)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
