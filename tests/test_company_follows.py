"""Unit tests cho follow idempotent và thông báo việc làm mới."""
from datetime import datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.company import Company, CompanyStatus
from app.models.company_follow import CompanyFollow
from app.models.notification import Notification
from app.models.user import User
from app.services.company_follow import follow_company, unfollow_company
from app.services.company_follow_notifications import (
    NOTIFICATION_TYPE,
    PublishedJobEvent,
    send_followed_company_job_notifications,
)


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Company.__table__,
            CompanyFollow.__table__,
            Notification.__table__,
        ],
    )
    return sessionmaker(bind=engine), engine


def test_follow_is_idempotent_and_unfollow_is_idempotent():
    factory, engine = _session_factory()
    db = factory()
    try:
        candidate = User(email="candidate@test.local", password="x", full_name="Candidate", role="candidate")
        employer = User(email="employer@test.local", password="x", full_name="Employer", role="employer")
        db.add_all([candidate, employer])
        db.flush()
        company = Company(
            employer_id=employer.id,
            name="Company",
            status=CompanyStatus.VERIFIED,
            is_draft=False,
        )
        db.add(company)
        db.commit()
        candidate_id = candidate.id
        company_id = company.id

        assert follow_company(db, candidate_id, company_id) is True
        assert follow_company(db, candidate_id, company_id) is False
        assert db.scalar(select(func.count(CompanyFollow.id))) == 1

        unfollow_company(db, candidate_id, company_id)
        unfollow_company(db, candidate_id, company_id)
        assert db.scalar(select(func.count(CompanyFollow.id))) == 0
    finally:
        db.close()
        engine.dispose()


def test_published_job_notification_is_deduplicated_on_retry():
    factory, engine = _session_factory()
    db = factory()
    try:
        candidate = User(email="candidate@test.local", password="x", full_name="Candidate", role="candidate")
        employer = User(email="employer@test.local", password="x", full_name="Employer", role="employer")
        db.add_all([candidate, employer])
        db.flush()
        company = Company(
            employer_id=employer.id,
            name="Company",
            status=CompanyStatus.VERIFIED,
            is_draft=False,
        )
        db.add(company)
        db.flush()
        db.add(CompanyFollow(candidate_id=candidate.id, company_id=company.id))
        db.commit()
        candidate_id = candidate.id
        company_id = company.id

        event = PublishedJobEvent(
            job_id=25,
            company_id=company_id,
            company_name=company.name,
            job_title="Backend Engineer",
            location="Hà Nội",
            salary_min=20_000_000,
            salary_max=30_000_000,
            is_salary_negotiable=False,
            published_at=datetime.utcnow() + timedelta(seconds=1),
        )
        db.close()

        assert send_followed_company_job_notifications(event, factory) == 1
        assert send_followed_company_job_notifications(event, factory) == 0

        verify = factory()
        try:
            notification = verify.scalar(select(Notification))
            assert notification.type == NOTIFICATION_TYPE
            assert notification.user_id == candidate_id
            assert notification.dedupe_key == "followed-company-job:25"
            assert "Backend Engineer" in notification.message
            assert "Hà Nội" in notification.message
        finally:
            verify.close()
    finally:
        if db.is_active:
            db.close()
        engine.dispose()
