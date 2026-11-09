from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class Industry(Base):
    __tablename__ = "industries"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

class Location(Base):
    __tablename__ = "locations"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

class Skill(Base):
    __tablename__ = "skills"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active")