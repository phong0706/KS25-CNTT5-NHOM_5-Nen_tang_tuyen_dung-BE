"""Router Quản trị Ngân hàng câu hỏi phỏng vấn (/api/admin/interview-questions).
Chỉ dành cho Quản trị viên (role admin).
"""
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.user import User
from app.schemas.interview import (
    InterviewQuestionCreateIn, InterviewQuestionOut, InterviewQuestionUpdateIn
)

router = APIRouter(prefix="/admin/interview-questions", tags=["Admin Interview Questions"])


@router.get("", summary="Admin lấy danh sách câu hỏi phỏng vấn")
def admin_list_questions(
    category_id: Optional[int] = Query(None, ge=1),
    level_id: Optional[int] = Query(None, ge=1),
    q: Optional[str] = Query(None),
    is_published: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    clauses = ["1=1"]
    params = {}
    if category_id:
        clauses.append("iq.category_id = :cat_id")
        params["cat_id"] = category_id
    if level_id:
        clauses.append("iq.level_id = :lvl_id")
        params["lvl_id"] = level_id
    if is_published is not None:
        clauses.append("iq.is_published = :is_pub")
        params["is_pub"] = is_published
    if q and q.strip():
        clauses.append("(iq.question LIKE :kw OR iq.answer_hint LIKE :kw)")
        params["kw"] = f"%{q.strip()}%"

    where_sql = " AND ".join(clauses)
    total = db.execute(text(f"SELECT COUNT(*) FROM interview_questions iq WHERE {where_sql}"), params).scalar() or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    offset = (page - 1) * page_size

    sql = f"""
        SELECT iq.id, iq.category_id, mc.name AS category_name,
               iq.level_id, ml.name AS level_name,
               iq.question, iq.answer_hint, iq.is_published, iq.created_at
        FROM interview_questions iq
        JOIN meta_categories mc ON iq.category_id = mc.id
        JOIN meta_levels ml ON iq.level_id = ml.id
        WHERE {where_sql}
        ORDER BY iq.id DESC
        LIMIT :limit OFFSET :offset
    """
    p_exec = {**params, "limit": page_size, "offset": offset}
    rows = db.execute(text(sql), p_exec).fetchall()

    items = [
        InterviewQuestionOut(
            id=r.id, category_id=r.category_id, category_name=r.category_name,
            level_id=r.level_id, level_name=r.level_name,
            question=r.question, answer_hint=r.answer_hint,
            is_published=bool(r.is_published), is_practiced=False,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


@router.post("", response_model=InterviewQuestionOut, status_code=status.HTTP_201_CREATED, summary="Tạo câu hỏi mới")
def admin_create_question(
    data: InterviewQuestionCreateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    cat = db.execute(text("SELECT id, name FROM meta_categories WHERE id = :id"), {"id": data.category_id}).fetchone()
    if not cat: raise HTTPException(status_code=400, detail="Lĩnh vực không hợp lệ.")
    lvl = db.execute(text("SELECT id, name FROM meta_levels WHERE id = :id"), {"id": data.level_id}).fetchone()
    if not lvl: raise HTTPException(status_code=400, detail="Cấp bậc không hợp lệ.")

    stmt = text("""
        INSERT INTO interview_questions (category_id, level_id, question, answer_hint, is_published)
        VALUES (:cat_id, :lvl_id, :question, :hint, :is_pub)
    """)
    res = db.execute(stmt, {
        "cat_id": data.category_id, "lvl_id": data.level_id,
        "question": data.question.strip(), "hint": data.answer_hint.strip(),
        "is_pub": 1 if data.is_published else 0,
    })
    db.commit()
    new_id = res.lastrowid
    return InterviewQuestionOut(
        id=new_id, category_id=data.category_id, category_name=cat.name,
        level_id=data.level_id, level_name=lvl.name,
        question=data.question.strip(), answer_hint=data.answer_hint.strip(),
        is_published=data.is_published, is_practiced=False,
    )


@router.put("/{qid}", response_model=InterviewQuestionOut, summary="Cập nhật câu hỏi")
def admin_update_question(
    qid: int,
    data: InterviewQuestionUpdateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    cur = db.execute(text("SELECT * FROM interview_questions WHERE id = :id"), {"id": qid}).fetchone()
    if not cur: raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi.")

    cat_id = data.category_id if data.category_id is not None else cur.category_id
    lvl_id = data.level_id if data.level_id is not None else cur.level_id
    q_text = data.question.strip() if data.question else cur.question
    hint_text = data.answer_hint.strip() if data.answer_hint else cur.answer_hint
    pub = (1 if data.is_published else 0) if data.is_published is not None else cur.is_published

    cat = db.execute(text("SELECT name FROM meta_categories WHERE id = :id"), {"id": cat_id}).fetchone()
    lvl = db.execute(text("SELECT name FROM meta_levels WHERE id = :id"), {"id": lvl_id}).fetchone()

    db.execute(text("""
        UPDATE interview_questions
        SET category_id = :cat_id, level_id = :lvl_id, question = :q, answer_hint = :h, is_published = :pub
        WHERE id = :id
    """), {"cat_id": cat_id, "lvl_id": lvl_id, "q": q_text, "h": hint_text, "pub": pub, "id": qid})
    db.commit()

    return InterviewQuestionOut(
        id=qid, category_id=cat_id, category_name=cat.name,
        level_id=lvl_id, level_name=lvl.name,
        question=q_text, answer_hint=hint_text,
        is_published=bool(pub), is_practiced=False,
    )


@router.delete("/{qid}", summary="Xóa câu hỏi")
def admin_delete_question(
    qid: int,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    cur = db.execute(text("SELECT id FROM interview_questions WHERE id = :id"), {"id": qid}).fetchone()
    if not cur: raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi.")
    db.execute(text("DELETE FROM interview_practice WHERE question_id = :qid"), {"qid": qid})
    db.execute(text("DELETE FROM interview_questions WHERE id = :qid"), {"qid": qid})
    db.commit()
    return {"status": "ok", "deleted_id": qid}
