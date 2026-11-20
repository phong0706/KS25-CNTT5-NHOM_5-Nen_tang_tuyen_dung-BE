import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.company import Company
from app.models.company_follow import CompanyFollow
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User
from app.routers.candidate_followed_companies import (
    follow_company,
    list_followed_companies,
    unfollow_company,
)
from app.services.notification import (
    NotificationType,
    notify_company_followers_about_job,
)


def test_candidate_follow_list_and_unfollow_company():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Company.__table__,
            Job.__table__,
            CompanyFollow.__table__,
        ],
    )

    with Session(engine) as db:
        employer = User(email="employer@example.com", password="x", full_name="Employer", role="employer")
        candidate = User(email="candidate@example.com", password="x", full_name="Candidate")
        db.add_all([employer, candidate])
        db.flush()
        company = Company(
            employer_id=employer.id,
            name="Company One",
            slug="company-one",
            is_visible=True,
            is_draft=False,
        )
        hidden_company = Company(
            employer_id=employer.id,
            name="Hidden Company",
            is_visible=False,
            is_draft=False,
        )
        db.add_all([company, hidden_company])
        db.commit()

        assert follow_company(company.id, db, candidate).is_following is True
        assert follow_company(company.id, db, candidate).is_following is True
        db.add(
            Job(
                employer_id=employer.id,
                company_id=company.id,
                title="Software Engineer",
                status="published",
            )
        )
        db.commit()

        followed = list_followed_companies("", 1, 10, db, candidate)
        assert followed.total == 1
        assert followed.items[0].id == company.id
        assert followed.items[0].active_jobs_count == 1

        assert unfollow_company(company.id, db, candidate).is_following is False
        assert list_followed_companies("", 1, 10, db, candidate).total == 0
        with pytest.raises(HTTPException) as error:
            follow_company(hidden_company.id, db, candidate)
        assert error.value.status_code == 404


def test_new_job_notifies_each_company_follower_once():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine, tables=[CompanyFollow.__table__, Notification.__table__]
    )

    with Session(engine) as db:
        db.add_all(
            [
                CompanyFollow(user_id=11, company_id=21),
                CompanyFollow(user_id=12, company_id=21),
                CompanyFollow(user_id=13, company_id=22),
            ]
        )
        db.commit()

        assert notify_company_followers_about_job(
            db,
            company_id=21,
            company_name="Công ty A",
            job_id=31,
            job_title="Kỹ sư phần mềm",
            actor_id=41,
        ) == 2
        assert notify_company_followers_about_job(
            db,
            company_id=21,
            company_name="Công ty A",
            job_id=31,
            job_title="Kỹ sư phần mềm",
            actor_id=41,
        ) == 0

        notifications = db.scalars(select(Notification)).all()
        assert len(notifications) == 2
        assert {item.user_id for item in notifications} == {11, 12}
        assert all(item.type == NotificationType.COMPANY_NEW_JOB for item in notifications)
        assert all(item.ref_type == "job" and item.ref_id == 31 for item in notifications)
