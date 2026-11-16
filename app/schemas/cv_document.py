"""Schema cho tài liệu CV (cv_documents)."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CVDocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    template_slug: str = Field(default="simple", max_length=50)
    content_json: str


class CVDocumentCreate(CVDocumentBase):
    pass


class CVDocumentUpdate(CVDocumentBase):
    version: int = Field(..., description="Phiên bản hiện tại để kiểm tra xung đột (OCC)")


class CVDocumentRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class CVDocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    template_slug: str
    version: int
    created_at: datetime
    updated_at: datetime


class CVDocumentOut(CVDocumentListItem):
    user_id: int
    content_json: str
