"""Script seed dữ liệu mẫu hồ sơ ứng viên vào MySQL (chạy một lần hoặc lặp lại an toàn)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models.candidate import CandidateProfile  # noqa: E402
from app.models.candidate_profile import (  # noqa: E402
    CandidateEducation,
    CandidateExperience,
)
from app.models.user import User  # noqa: E402


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.role == "candidate").order_by(User.id.asc()))
        if not user:
            user = User(
                email="candidate@techrecruit.vn",
                password=hash_password(os.getenv("SEED_USER_PASSWORD", "TechRecruit2026!")),
                full_name="Nguyễn Minh Anh",
                phone="0912345678",
                role="candidate",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if not user.phone:
                user.phone = "0912345678"
                db.add(user)
                db.commit()

        profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if not profile:
            profile = CandidateProfile(
                user_id=user.id,
                headline="Senior Backend Engineer (Python / FastAPI)",
                birth_date="1997-08-15",
                location="Hà Nội",
                linkedin_url="https://linkedin.com/in/minh-anh-dev",
                github_url="https://github.com/minhanh-dev",
                portfolio_url="https://minhanh.dev",
                bio="Kỹ sư phần mềm với hơn 4 năm kinh nghiệm xây dựng hệ thống API hiệu năng cao bằng Python, FastAPI và MySQL.",
                skills_json=json.dumps(["Python", "FastAPI", "MySQL", "Docker", "Redis"]),
                is_searchable=True,
            )
            db.add(profile)
            db.commit()

        exp_exists = db.scalar(
            select(CandidateExperience).where(CandidateExperience.user_id == user.id)
        )
        if not exp_exists:
            db.add(
                CandidateExperience(
                    user_id=user.id,
                    title="Backend Engineer",
                    company="Rikkeisoft",
                    start_month="2022-03",
                    end_month=None,
                    is_current=True,
                    description="Phát triển hệ thống tuyển dụng và microservices bằng FastAPI, tối ưu truy vấn MySQL giảm 40% độ trễ API.",
                )
            )
            db.commit()

        print(f"[SEED] Đã seed hồ sơ ứng viên cho user_id={user.id} ({user.email})")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

