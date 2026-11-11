# Import các schema danh mục (Industry, Location, Skill)
from app.schemas.catalog_schema import (
    CatalogBase,
    CatalogCreate,
    CatalogUpdate,
    CatalogResponse
)

# Import các schema báo cáo vi phạm (Report)
from app.schemas.report_schema import (
    ReportCreate,
    ReportUpdate,
    ReportResponse
)

__all__ = [
    "CatalogBase",
    "CatalogCreate", 
    "CatalogUpdate",
    "CatalogResponse",
    "ReportCreate",
    "ReportUpdate",
    "ReportResponse",
]

