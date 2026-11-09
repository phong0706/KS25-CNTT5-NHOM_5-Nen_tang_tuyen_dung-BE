from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)