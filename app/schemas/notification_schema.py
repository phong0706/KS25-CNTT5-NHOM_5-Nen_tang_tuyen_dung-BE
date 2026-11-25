"""Schema cho Notification - Thông báo."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    """Dữ liệu thông báo trả về cho FE."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    notification_type: str
    title: str
    message: str
    related_url: str | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None
