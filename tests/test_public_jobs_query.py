import warnings
from datetime import date, timedelta
import unittest

from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.db.session import Base
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.services.public_jobs_query import query_public_jobs


class PublicJobsQueryTests(unittest.TestCase):
    def test_distinct_company_query_joins_tables_used_by_filters(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            company = Company(
                employer_id=1,
                name="Verified demo company",
                status=CompanyStatus.VERIFIED,
                verification_status="da_xac_minh",
                is_verified=True,
                is_visible=True,
                is_draft=False,
            )
            db.add(company)
            db.flush()
            db.add_all(
                [
                    Job(
                        employer_id=1,
                        company_id=company.id,
                        title="Older posting",
                        status="published",
                        deadline=date.today() + timedelta(days=5),
                    ),
                    Job(
                        employer_id=1,
                        company_id=company.id,
                        title="Newest posting",
                        status="published",
                        deadline=date.today() + timedelta(days=10),
                    ),
                ]
            )
            db.commit()

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", SAWarning)
                result = query_public_jobs(
                    db,
                    q="",
                    location="",
                    level="",
                    work_type="",
                    category="",
                    company_id=None,
                    company="",
                    salary_min=None,
                    salary_max=None,
                    skills="",
                    sort="newest",
                    distinct_company=True,
                    page=1,
                    page_size=10,
                    current_user=None,
                )

            cartesian_warnings = [
                warning
                for warning in caught
                if issubclass(warning.category, SAWarning)
                and "cartesian product" in str(warning.message).lower()
            ]
            self.assertFalse(cartesian_warnings)
            self.assertEqual(result.total, 1)
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].title, "Newest posting")

    def test_search_by_company_name_as_keyword_and_company_facet(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            company = Company(
                employer_id=2,
                name="Rikkeisoft",
                slug="rikkeisoft",
                status=CompanyStatus.VERIFIED,
                verification_status="da_xac_minh",
                is_verified=True,
                is_visible=True,
            )
            db.add(company)
            db.flush()
            db.add_all(
                [
                    Job(
                        employer_id=2,
                        company_id=company.id,
                        title="Cloud DevOps Engineer (AWS & Terraform)",
                        status="published",
                        deadline=date.today() + timedelta(days=10),
                    ),
                    Job(
                        employer_id=2,
                        company_id=company.id,
                        title="Principal Python Architect",
                        status="published",
                        deadline=date.today() + timedelta(days=10),
                    ),
                ]
            )
            db.commit()

            # 1. Tìm theo từ khóa 'rikkei' (tên công ty) dù title không chứa từ này
            res_kw = query_public_jobs(
                db, q="rikkei", location="", level="", work_type="", category="",
                company_id=None, company="", salary_min=None, salary_max=None,
                skills="", sort="newest", distinct_company=False, page=1, page_size=10,
                current_user=None,
            )
            self.assertEqual(res_kw.total, 2)
            self.assertEqual(len(res_kw.items), 2)
            self.assertEqual(res_kw.facets.company[0].label, "Rikkeisoft")
            self.assertEqual(res_kw.facets.company[0].value, "rikkeisoft")

            # 2. Tìm vừa q='rikkei' vừa company='rikkeisoft' (trường hợp người dùng gặp lỗi)
            res_both = query_public_jobs(
                db, q="rikkei", location="", level="", work_type="", category="",
                company_id=None, company="rikkeisoft", salary_min=None, salary_max=None,
                skills="", sort="newest", distinct_company=False, page=1, page_size=10,
                current_user=None,
            )
            self.assertEqual(res_both.total, 2)
            self.assertEqual(len(res_both.items), 2)

            # 3. Tìm từ khóa không tồn tại
            res_none = query_public_jobs(
                db, q="nonexistent", location="", level="", work_type="", category="",
                company_id=None, company="", salary_min=None, salary_max=None,
                skills="", sort="newest", distinct_company=False, page=1, page_size=10,
                current_user=None,
            )
            self.assertEqual(res_none.total, 0)


if __name__ == "__main__":
    unittest.main()
