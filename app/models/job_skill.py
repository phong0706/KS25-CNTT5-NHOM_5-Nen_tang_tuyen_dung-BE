from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        Index("idx_job_skills_job_skill", "job_id", "skill_id", unique=True),
        Index("idx_job_skills_skill_job", "skill_id", "job_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)