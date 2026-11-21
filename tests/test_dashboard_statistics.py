import os
import secrets
import unittest
from datetime import datetime

os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))
os.environ.setdefault("DB_PASSWORD", "statistics-test-only")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.models.application import Application, Interview
from app.models.catalog import Industry
from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaCategory
from app.models.user import User
from app.routers.statistics import router


class DashboardStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        tables = [
            User.__table__,
            Company.__table__,
            Industry.__table__,
            MetaCategory.__table__,
            Job.__table__,
            Application.__table__,
            Interview.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=tables)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False)

        with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id=1,
                        email="employer@example.test",
                        password="unused",
                        full_name="Employer",
                        role="employer",
                        is_active=True,
                        created_at=datetime(2026, 11, 2, 9),
                    ),
                    User(
                        id=2,
                        email="other@example.test",
                        password="unused",
                        full_name="Other Employer",
                        role="employer",
                        is_active=True,
                        created_at=datetime(2026, 10, 1, 9),
                    ),
                    User(
                        id=3,
                        email="admin@example.test",
                        password="unused",
                        full_name="Admin",
                        role="admin",
                        is_active=True,
                        created_at=datetime(2026, 11, 3, 10),
                    ),
                    User(
                        id=4,
                        email="candidate@example.test",
                        password="unused",
                        full_name="Candidate",
                        role="candidate",
                        is_active=True,
                        created_at=datetime(2026, 11, 3, 11),
                    ),
                    Industry(id=5, name="Công nghệ", status="active"),
                    MetaCategory(id=10, slug="software", name="Phần mềm"),
                    Company(
                        id=20,
                        employer_id=1,
                        name="Test company",
                        industry_id=5,
                        is_draft=False,
                        is_verified=True,
                        status=CompanyStatus.VERIFIED,
                        created_at=datetime(2026, 11, 3, 23, 59, 59),
                    ),
                    Job(
                        id=30,
                        employer_id=1,
                        company_id=20,
                        category_id=10,
                        title="Published job",
                        status="PUBLISHED",
                        views_count=20,
                        created_at=datetime(2026, 11, 3, 23, 59, 59),
                    ),
                    Job(
                        id=31,
                        employer_id=1,
                        company_id=20,
                        category_id=10,
                        title="Draft job",
                        status="draft",
                        views_count=2,
                        created_at=datetime(2026, 10, 1, 9),
                    ),
                    Job(
                        id=32,
                        employer_id=1,
                        company_id=20,
                        category_id=10,
                        title="Closed job",
                        status="closed",
                        views_count=0,
                        created_at=datetime(2026, 10, 2, 9),
                    ),
                    Job(
                        id=33,
                        employer_id=2,
                        title="Other employer job",
                        status="published",
                        views_count=100,
                        created_at=datetime(2026, 11, 2, 9),
                    ),
                    Application(
                        id=40,
                        candidate_id=4,
                        job_id=30,
                        status="OFFERED",
                        viewed_at=None,
                        created_at=datetime(2026, 11, 2, 12),
                    ),
                    Application(
                        id=41,
                        candidate_id=4,
                        job_id=30,
                        status="submitted",
                        viewed_at=None,
                        created_at=datetime(2026, 11, 3, 23, 59, 59),
                    ),
                    Application(
                        id=42,
                        candidate_id=4,
                        job_id=30,
                        status="REJECTED",
                        viewed_at=None,
                        created_at=datetime(2026, 10, 1, 12),
                    ),
                    Application(
                        id=43,
                        candidate_id=4,
                        job_id=33,
                        status="OFFERED",
                        viewed_at=None,
                        created_at=datetime(2026, 11, 2, 13),
                    ),
                ]
            )
            db.commit()

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        self.app = FastAPI()
        self.app.include_router(router, prefix="/api")
        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    @staticmethod
    def auth_headers(user_id, role):
        return {
            "Authorization": f"Bearer {create_access_token(user_id, role)}",
        }

    def test_employer_stats_scope_applications_to_owner_and_date_range(self):
        response = self.client.get(
            "/api/employer/dashboard/stats",
            params={"from_date": "2026-11-02", "to_date": "2026-11-03"},
            headers=self.auth_headers(1, "employer"),
        )

        self.assertEqual(response.status_code, 200, response.text)
        stats = response.json()
        self.assertEqual(stats["total_jobs"], 3)
        self.assertEqual(stats["active_jobs"], 1)
        self.assertEqual(stats["draft_jobs"], 1)
        self.assertEqual(stats["closed_jobs"], 1)
        self.assertEqual(stats["total_views"], 22)
        self.assertEqual(stats["period_jobs_created"], 1)
        self.assertEqual(stats["total_applications"], 2)
        self.assertEqual(stats["applications_by_status"], {"offered": 1, "submitted": 1})
        self.assertEqual(stats["unviewed_applications"], 2)
        self.assertEqual(stats["hiring_rate"], 50.0)

    def test_admin_stats_filter_activity_and_group_by_company_industry(self):
        response = self.client.get(
            "/api/admin/dashboard/stats",
            params={"from_date": "2026-11-02", "to_date": "2026-11-03"},
            headers=self.auth_headers(3, "admin"),
        )

        self.assertEqual(response.status_code, 200, response.text)
        stats = response.json()
        self.assertEqual(stats["total_users"], 4)
        self.assertEqual(stats["users_by_role"], {"admin": 1, "candidate": 1, "employer": 2})
        self.assertEqual(stats["new_users_in_period"], 3)
        self.assertEqual(stats["total_companies"], 1)
        self.assertEqual(stats["companies_by_industry"], [
            {"industry_id": 5, "industry_name": "Công nghệ", "count": 1},
        ])
        self.assertEqual(stats["total_jobs"], 4)
        self.assertEqual(stats["jobs_by_industry"], [
            {"category_id": 10, "category_name": "Phần mềm", "count": 1},
        ])
        self.assertEqual(stats["total_applications"], 3)
        self.assertEqual(stats["applications_by_day"], [
            {"date": "2026-11-02", "count": 2},
            {"date": "2026-11-03", "count": 1},
        ])

    def test_date_range_validation_and_role_access(self):
        admin_headers = self.auth_headers(3, "admin")
        invalid_date = self.client.get(
            "/api/admin/dashboard/stats",
            params={"from_date": "not-a-date"},
            headers=admin_headers,
        )
        reversed_range = self.client.get(
            "/api/admin/dashboard/stats",
            params={"from_date": "2026-11-04", "to_date": "2026-11-03"},
            headers=admin_headers,
        )
        forbidden = self.client.get(
            "/api/admin/dashboard/stats",
            headers=self.auth_headers(1, "employer"),
        )

        self.assertEqual(invalid_date.status_code, 400)
        self.assertEqual(reversed_range.status_code, 400)
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
