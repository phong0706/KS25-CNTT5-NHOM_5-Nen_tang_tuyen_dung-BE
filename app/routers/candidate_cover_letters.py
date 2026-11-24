"""Router quản lý thư giới thiệu cá nhân (/api/candidate/cover-letters)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional

from app.db.session import get_db
from app.core.security import role_required

router = APIRouter(prefix="/candidate/cover-letters", tags=["Candidate Cover Letters"])

class CoverLetterItem(BaseModel):
    id: int
    title: str
    content: str
    created_at: str

class CoverLetterCreate(BaseModel):
    title: str
    content: str

@router.get("", response_model=List[CoverLetterItem], summary="Danh sách thư giới thiệu của ứng viên")
def get_my_cover_letters(db: Session = Depends(get_db), current_user = Depends(role_required("candidate"))):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    rows = db.execute(
        text("SELECT id, title, content, created_at FROM candidate_cover_letters WHERE candidate_id = :cid ORDER BY updated_at DESC"),
        {"cid": current_user.id}
    ).fetchall()

    return [
        CoverLetterItem(
            id=r.id,
            title=r.title,
            content=r.content,
            created_at=str(r.created_at)
        )
        for r in rows
    ]

@router.post("", response_model=CoverLetterItem, status_code=status.HTTP_201_CREATED, summary="Tạo thư giới thiệu mới")
def create_cover_letter(data: CoverLetterCreate, db: Session = Depends(get_db), current_user = Depends(role_required("candidate"))):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    stmt = text("INSERT INTO candidate_cover_letters (candidate_id, title, content) VALUES (:cid, :title, :content)")
    res = db.execute(stmt, {"cid": current_user.id, "title": data.title.strip(), "content": data.content})
    db.commit()
    new_id = res.lastrowid

    row = db.execute(text("SELECT id, title, content, created_at FROM candidate_cover_letters WHERE id = :id"), {"id": new_id}).fetchone()
    return CoverLetterItem(id=row.id, title=row.title, content=row.content, created_at=str(row.created_at))

@router.delete("/{id}", summary="Xoá thư giới thiệu")
def delete_cover_letter(id: int, db: Session = Depends(get_db), current_user = Depends(role_required("candidate"))):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    res = db.execute(text("DELETE FROM candidate_cover_letters WHERE id = :id AND candidate_id = :cid"), {"id": id, "cid": current_user.id})
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thư giới thiệu")
    return {"status": "ok", "message": "Đã xoá thư giới thiệu thành công"}
