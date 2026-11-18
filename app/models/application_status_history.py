"""Re-export ApplicationStatusHistory từ app.models.application để tránh trùng __tablename__."""
from app.models.application import ApplicationStatusHistory  # noqa: F401
