"""Router câu hỏi phỏng vấn & tiến độ luyện tập cho ứng viên."""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_optional_user, role_required
from app.db.session import get_db
from app.models.user import User
from app.schemas.interview import (
    InterviewQuestionOut, InterviewQuestionsListOut, PracticeStatsOut, PracticeToggleOut
)

router = APIRouter(prefix="/interview-questions", tags=["Interview Questions"])


def _build_filter(category_id: Optional[int], level_id: Optional[int], q: Optional[str]):
    clauses = ["iq.is_published = 1"]
    params = {}
    if category_id:
        clauses.append("iq.category_id = :cat_id")
        params["cat_id"] = category_id
    if level_id:
        clauses.append("iq.level_id = :lvl_id")
        params["lvl_id"] = level_id
    if q and q.strip():
        clauses.append("(iq.question LIKE :kw OR iq.answer_hint LIKE :kw)")
        params["kw"] = f"%{q.strip()}%"
    return " AND ".join(clauses), params


@router.get("", response_model=InterviewQuestionsListOut, summary="Danh sách câu hỏi phỏng vấn")
def list_questions(
    category_id: Optional[int] = Query(None, ge=1),
    level_id: Optional[int] = Query(None, ge=1),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    where_sql, params = _build_filter(category_id, level_id, q)

    # 1. Đếm tổng số câu hỏi theo bộ lọc
    count_sql = f"SELECT COUNT(*) FROM interview_questions iq WHERE {where_sql}"
    total = db.execute(text(count_sql), params).scalar() or 0

    # 2. Đếm số câu hỏi đã luyện theo bộ lọc (chỉ áp dụng cho candidate)
    practiced_count = 0
    practiced_ids = set()
    if user and user.id and user.role == "candidate":
        p_stats_sql = f"""
            SELECT COUNT(DISTINCT ip.question_id)
            FROM interview_practice ip
            JOIN interview_questions iq ON ip.question_id = iq.id
            WHERE ip.candidate_id = :uid AND {where_sql}
        """
        p_params = {**params, "uid": user.id}
        practiced_count = db.execute(text(p_stats_sql), p_params).scalar() or 0

        # Lấy danh sách question_id đã luyện
        p_ids_sql = "SELECT question_id FROM interview_practice WHERE candidate_id = :uid"
        practiced_ids = {r[0] for r in db.execute(text(p_ids_sql), {"uid": user.id}).fetchall()}

    percentage = round((practiced_count / total * 100), 1) if total > 0 else 0.0
    stats = PracticeStatsOut(practiced_count=practiced_count, total_count=total, percentage=percentage)

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0
    offset = (page - 1) * page_size

    list_sql = f"""
        SELECT iq.id, iq.category_id, mc.name AS category_name,
               iq.level_id, ml.name AS level_name,
               iq.question, iq.answer_hint, iq.is_published, iq.created_at
        FROM interview_questions iq
        JOIN meta_categories mc ON iq.category_id = mc.id
        JOIN meta_levels ml ON iq.level_id = ml.id
        WHERE {where_sql}
        ORDER BY iq.id ASC
        LIMIT :limit OFFSET :offset
    """
    p_exec = {**params, "limit": page_size, "offset": offset}
    rows = db.execute(text(list_sql), p_exec).fetchall()

    items = [
        InterviewQuestionOut(
            id=r.id, category_id=r.category_id, category_name=r.category_name,
            level_id=r.level_id, level_name=r.level_name,
            question=r.question, answer_hint=r.answer_hint,
            is_published=bool(r.is_published), is_practiced=(r.id in practiced_ids),
            created_at=r.created_at,
        )
        for r in rows
    ]

    return InterviewQuestionsListOut(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=total_pages, stats=stats
    )


@router.get("/random", response_model=Optional[InterviewQuestionOut], summary="Lấy câu hỏi ngẫu nhiên")
def get_random_question(
    category_id: Optional[int] = Query(None, ge=1),
    level_id: Optional[int] = Query(None, ge=1),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    where_sql, params = _build_filter(category_id, level_id, q)
    sql = f"""
        SELECT iq.id, iq.category_id, mc.name AS category_name,
               iq.level_id, ml.name AS level_name,
               iq.question, iq.answer_hint, iq.is_published, iq.created_at
        FROM interview_questions iq
        JOIN meta_categories mc ON iq.category_id = mc.id
        JOIN meta_levels ml ON iq.level_id = ml.id
        WHERE {where_sql}
        ORDER BY RAND() LIMIT 1
    """
    row = db.execute(text(sql), params).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy câu hỏi phù hợp.")

    is_practiced = False
    if user and user.id and user.role == "candidate":
        p_row = db.execute(
            text("SELECT 1 FROM interview_practice WHERE candidate_id = :uid AND question_id = :qid"),
            {"uid": user.id, "qid": row.id}
        ).fetchone()
        is_practiced = bool(p_row)

    return InterviewQuestionOut(
        id=row.id, category_id=row.category_id, category_name=row.category_name,
        level_id=row.level_id, level_name=row.level_name,
        question=row.question, answer_hint=row.answer_hint,
        is_published=bool(row.is_published), is_practiced=is_practiced,
        created_at=row.created_at,
    )


@router.post("/{question_id}/practice", response_model=PracticeToggleOut, summary="Đánh dấu đã luyện câu hỏi")
def toggle_practice(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("candidate")),
):
    q_row = db.execute(
        text("SELECT id FROM interview_questions WHERE id = :qid AND is_published = 1"),
        {"qid": question_id}
    ).fetchone()
    if not q_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Câu hỏi không tồn tại.")

    exist = db.execute(
        text("SELECT id FROM interview_practice WHERE candidate_id = :uid AND question_id = :qid"),
        {"uid": current_user.id, "qid": question_id}
    ).fetchone()

    if exist:
        db.execute(
            text("DELETE FROM interview_practice WHERE candidate_id = :uid AND question_id = :qid"),
            {"uid": current_user.id, "qid": question_id}
        )
        db.commit()
        practiced = False
    else:
        db.execute(
            text("INSERT INTO interview_practice (candidate_id, question_id) VALUES (:uid, :qid) ON DUPLICATE KEY UPDATE practiced_at = CURRENT_TIMESTAMP"),
            {"uid": current_user.id, "qid": question_id}
        )
        db.commit()
        practiced = True

    total = db.execute(text("SELECT COUNT(*) FROM interview_questions WHERE is_published = 1")).scalar() or 0
    practiced_count = db.execute(
        text("SELECT COUNT(*) FROM interview_practice WHERE candidate_id = :uid"),
        {"uid": current_user.id}
    ).scalar() or 0
    pct = round((practiced_count / total * 100), 1) if total > 0 else 0.0

    return PracticeToggleOut(
        status="ok", practiced=practiced, question_id=question_id,
        stats=PracticeStatsOut(practiced_count=practiced_count, total_count=total, percentage=pct)
    )
