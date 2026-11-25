"""Re-export SavedJob từ app.models.job để tránh trùng __tablename__."""
from app.models.job import SavedJob  # noqa: F401
