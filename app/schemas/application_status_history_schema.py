"""Schema cho ApplicationStatusHistory - Lịch sử thay đổi trạng thái đơn ứng tuyển."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# ApplicationStatusHistory
# ---------------------------------------------------------------------------
class ApplicationStatusHistoryCreate(BaseModel):
    """Dữ liệu khi tạo bản ghi lịch sử (hệ thống tự động tạo khi đổi status)."""
    application_id: int = Field(examples=[1])
    old_status: str | None = Field(default=None, examples=["SUBMITTED"])
    new_status: str = Field(examples=["REVIEWING"])
    changed_by_user_id: int | None = Field(default=None, examples=[2])


class ApplicationStatusHistoryOut(BaseModel):
    """Dữ liệu lịch sử trả về cho FE."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    old_status: str | None
    new_status: str
    changed_at: datetime
    changed_by_user_id: int | None
