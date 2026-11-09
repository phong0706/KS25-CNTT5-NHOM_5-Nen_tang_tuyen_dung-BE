from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobSearchOut(BaseModel):
    id: int
    title: str
    description: str | None
    company_name: str
    industry_name: str
    location_name: str
    deadline: datetime
    created_at: datetime


class SavedJobDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company_name: str
    industry_name: str
    location_name: str
    deadline: datetime
    saved_at: datetime