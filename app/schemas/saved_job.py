from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SavedJobCreate(BaseModel):
    candidate_profile_id: int
    job_id: int


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_profile_id: int
    job_id: int
    saved_at: datetime