"""
backend/tests/unit/test_career_roadmap.py
Kiểm thử lộ trình sự nghiệp _infer_candidate_context không bị lỗi SQL 1054.
"""
from app.db.session import SessionLocal
from app.models.user import User
from app.services.career_roadmap_resolver import _infer_candidate_context

def test_infer_candidate_context_no_sql_error():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == "candidate").first()
        assert user is not None, "Candidate must exist"
        
        # Call _infer_candidate_context directly
        skills, family, level = _infer_candidate_context(db, user.id, [], None, None)
        assert isinstance(skills, list)
    finally:
        db.close()
