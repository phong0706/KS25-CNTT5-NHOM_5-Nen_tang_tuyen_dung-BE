"""Kiểm thử hồi quy đảm bảo CandidateProfile chỉ có 1 định nghĩa duy nhất (không dùng extend_existing)
và các endpoint hồ sơ ứng viên (/api/candidate/profile, /api/profiles/me) hoạt động ổn định.
"""
from pathlib import Path
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import Base, SessionLocal
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.user import User


def test_single_candidate_profile_definition_without_extend_existing():
    assert not hasattr(CandidateProfile, "__table_args__") or "extend_existing" not in (
        CandidateProfile.__table_args__ if isinstance(CandidateProfile.__table_args__, dict) else {}
    )
    table = Base.metadata.tables["candidate_profiles"]
    expected_cols = {
        "id", "user_id", "headline", "birth_date", "location",
        "linkedin_url", "github_url", "portfolio_url", "bio", "skills_json",
        "level", "work_type", "expected_salary", "is_searchable", "version",
        "date_of_birth", "address", "desired_position", "desired_salary",
        "summary", "is_public", "created_at", "updated_at",
    }
    assert expected_cols.issubset(set(table.columns.keys()))


def test_candidate_profile_endpoints_return_200_no_500():
    client = TestClient(app)
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    cand = User(
        email=f"cand_model_{tag}@test.vn",
        full_name="Ứng viên Kiểm thử Model",
        password=hash_password("Pass123!"),
        role="candidate",
        is_active=True,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    headers = {"Authorization": f"Bearer {create_access_token(cand.id, cand.role)}"}

    try:
        # GET /api/candidate/profile tự khởi tạo hồ sơ nếu chưa có -> 200
        r1 = client.get("/api/candidate/profile", headers=headers)
        assert r1.status_code == 200
        assert r1.json()["email"] == cand.email

        # GET /api/profiles/me tải kèm joinedload(skills, experiences, educations, cvs) -> 200
        r2 = client.get("/api/profiles/me", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["user_id"] == cand.id
    finally:
        db.rollback()
        obj = db.get(User, cand.id)
        if obj:
            db.delete(obj)
            db.commit()
        db.close()
