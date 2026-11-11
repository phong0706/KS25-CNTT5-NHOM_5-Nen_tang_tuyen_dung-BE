"""CRUD cho các bảng danh mục: Industry, Location, Skill.

Tính năng:
- Kiểm tra tên không trùng
- Không xóa khi đang được sử dụng
- Soft delete (ẩn bằng cách đổi status)
"""
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.catalog import Industry, Location, Skill
from app.schemas.catalog_schema import CatalogCreate, CatalogUpdate


# ============================================
# GENERIC FUNCTIONS (dùng chung cho 3 models)
# ============================================

def get_all_catalogs(db: Session, model_class, status: str | None = None) -> list:
    """Lấy tất cả danh mục. Nếu status=None thì lấy hết, ngược lại lọc theo status."""
    query = select(model_class).order_by(model_class.name)
    if status:
        query = query.where(model_class.status == status)
    return list(db.scalars(query))


def get_catalog_by_id(db: Session, model_class, catalog_id: int):
    """Lấy 1 danh mục theo ID."""
    return db.get(model_class, catalog_id)


def get_catalog_by_name(db: Session, model_class, name: str):
    """Kiểm tra tên đã tồn tại chưa."""
    return db.scalar(select(model_class).where(model_class.name == name))


def create_catalog(db: Session, model_class, data: CatalogCreate):
    """Tạo mới danh mục. Raise exception nếu tên đã tồn tại."""
    existing = get_catalog_by_name(db, model_class, data.name)
    if existing:
        raise ValueError(f"Tên '{data.name}' đã tồn tại")
    
    catalog = model_class(**data.model_dump())
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


def update_catalog(db: Session, model_class, catalog, data: CatalogUpdate):
    """Cập nhật danh mục. Kiểm tra tên trùng nếu đổi tên."""
    update_data = data.model_dump(exclude_unset=True)
    
    # Nếu đổi tên, kiểm tra tên mới có trùng không
    if "name" in update_data:
        existing = get_catalog_by_name(db, model_class, update_data["name"])
        if existing and existing.id != catalog.id:
            raise ValueError(f"Tên '{update_data['name']}' đã tồn tại")
    
    for field, value in update_data.items():
        setattr(catalog, field, value)
    
    db.commit()
    db.refresh(catalog)
    return catalog


def soft_delete_catalog(db: Session, catalog):
    """Soft delete: đổi status thành 'inactive' thay vì xóa hẳn."""
    catalog.status = "inactive"
    db.commit()
    db.refresh(catalog)
    return catalog


def check_catalog_in_use(db: Session, model_class, catalog_id: int) -> bool:
    """
    Kiểm tra danh mục có đang được sử dụng không.
    
    TODO: Cần implement logic kiểm tra dựa vào các bảng liên quan:
    - Industry: kiểm tra trong bảng jobs, companies, user_profiles...
    - Location: kiểm tra trong bảng jobs, companies...
    - Skill: kiểm tra trong bảng user_skills, job_skills...
    
    Hiện tại trả về False (chưa được sử dụng).
    """
    return False


# ============================================
# INDUSTRY FUNCTIONS
# ============================================

def get_industries(db: Session, status: str | None = "active") -> list[Industry]:
    """Lấy danh sách ngành nghề."""
    return get_all_catalogs(db, Industry, status)


def get_industry(db: Session, industry_id: int) -> Industry | None:
    """Lấy 1 ngành nghề theo ID."""
    return get_catalog_by_id(db, Industry, industry_id)


def create_industry(db: Session, data: CatalogCreate) -> Industry:
    """Tạo ngành nghề mới."""
    return create_catalog(db, Industry, data)


def update_industry(db: Session, industry: Industry, data: CatalogUpdate) -> Industry:
    """Cập nhật ngành nghề."""
    return update_catalog(db, Industry, industry, data)


def delete_industry(db: Session, industry: Industry) -> Industry:
    """Soft delete ngành nghề."""
    if check_catalog_in_use(db, Industry, industry.id):
        raise ValueError("Không thể xóa ngành nghề đang được sử dụng")
    return soft_delete_catalog(db, industry)


# ============================================
# LOCATION FUNCTIONS
# ============================================

def get_locations(db: Session, status: str | None = "active") -> list[Location]:
    """Lấy danh sách địa điểm."""
    return get_all_catalogs(db, Location, status)


def get_location(db: Session, location_id: int) -> Location | None:
    """Lấy 1 địa điểm theo ID."""
    return get_catalog_by_id(db, Location, location_id)


def create_location(db: Session, data: CatalogCreate) -> Location:
    """Tạo địa điểm mới."""
    return create_catalog(db, Location, data)


def update_location(db: Session, location: Location, data: CatalogUpdate) -> Location:
    """Cập nhật địa điểm."""
    return update_catalog(db, Location, location, data)


def delete_location(db: Session, location: Location) -> Location:
    """Soft delete địa điểm."""
    if check_catalog_in_use(db, Location, location.id):
        raise ValueError("Không thể xóa địa điểm đang được sử dụng")
    return soft_delete_catalog(db, location)


# ============================================
# SKILL FUNCTIONS
# ============================================

def get_skills(db: Session, status: str | None = "active") -> list[Skill]:
    """Lấy danh sách kỹ năng."""
    return get_all_catalogs(db, Skill, status)


def get_skill(db: Session, skill_id: int) -> Skill | None:
    """Lấy 1 kỹ năng theo ID."""
    return get_catalog_by_id(db, Skill, skill_id)


def create_skill(db: Session, data: CatalogCreate) -> Skill:
    """Tạo kỹ năng mới."""
    return create_catalog(db, Skill, data)


def update_skill(db: Session, skill: Skill, data: CatalogUpdate) -> Skill:
    """Cập nhật kỹ năng."""
    return update_catalog(db, Skill, skill, data)


def delete_skill(db: Session, skill: Skill) -> Skill:
    """Soft delete kỹ năng."""
    if check_catalog_in_use(db, Skill, skill.id):
        raise ValueError("Không thể xóa kỹ năng đang được sử dụng")
    return soft_delete_catalog(db, skill)
