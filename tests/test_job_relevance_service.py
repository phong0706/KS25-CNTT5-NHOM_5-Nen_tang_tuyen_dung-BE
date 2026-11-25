"""Unit test kiểm thử tính điểm độ phù hợp cho việc làm (TDD)."""
import unittest
from datetime import datetime, timedelta

from app.services.job_relevance_service import compute_relevance_score


class JobRelevanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now()

    def test_relevance_with_keyword_exact_title_ranks_highest(self):
        # Tin 1: Tiêu đề khớp chính xác "React Developer"
        j1 = {
            "id": 1,
            "title": "React Developer",
            "skills": ["React", "JavaScript"],
            "company_name": "Tech Corp",
            "salary_min": 20_000_000,
            "salary_max": 30_000_000,
            "is_salary_negotiable": False,
            "is_verified": True,
            "created_at": self.now,
        }
        # Tin 2: Tiêu đề chứa "Senior React & Design System Engineer"
        j2 = {
            "id": 2,
            "title": "Senior React & Design System Engineer",
            "skills": ["React", "TypeScript"],
            "company_name": "VNG",
            "salary_min": 35_000_000,
            "salary_max": 52_000_000,
            "is_salary_negotiable": False,
            "is_verified": True,
            "created_at": self.now,
        }
        # Tin 3: Tiêu đề không có chữ React, chỉ có trong kỹ năng
        j3 = {
            "id": 3,
            "title": "Frontend Engineer",
            "skills": ["React", "CSS"],
            "company_name": "FPT",
            "salary_min": 20_000_000,
            "salary_max": 30_000_000,
            "is_salary_negotiable": False,
            "is_verified": True,
            "created_at": self.now,
        }

        s1 = compute_relevance_score(j1, keyword="React Developer")
        s2 = compute_relevance_score(j2, keyword="React Developer")
        s3 = compute_relevance_score(j3, keyword="React Developer")

        self.assertGreater(s1, s2, "Tin khớp chính xác tiêu đề phải có điểm cao hơn tin chỉ chứa 1 phần")
        self.assertGreater(s2, s3, "Tin có tiêu đề chứa từ khóa phải cao hơn tin chỉ có trong skills")

    def test_relevance_with_candidate_profile_match_score(self):
        j_high_match = {
            "id": 10,
            "title": "Backend Python Engineer",
            "skills": ["Python", "FastAPI"],
            "company_name": "ABC",
            "salary_min": 30_000_000,
            "salary_max": 45_000_000,
            "is_salary_negotiable": False,
            "is_verified": True,
            "created_at": self.now,
        }
        j_low_match = {
            "id": 11,
            "title": "Java Spring Boot Developer",
            "skills": ["Java", "Spring Boot"],
            "company_name": "XYZ",
            "salary_min": 30_000_000,
            "salary_max": 45_000_000,
            "is_salary_negotiable": False,
            "is_verified": True,
            "created_at": self.now,
        }

        profile = {"skills": ["Python", "FastAPI"], "level": "Senior"}
        s_high = compute_relevance_score(j_high_match, candidate_profile=profile, match_score=95.0)
        s_low = compute_relevance_score(j_low_match, candidate_profile=profile, match_score=20.0)

        self.assertGreater(s_high, s_low, "Tin có match_score 95% phải có điểm phù hợp cao hơn tin 20%")

    def test_relevance_guest_without_keyword_favors_quality_jobs(self):
        # Khách vãng lai: Tin có lương rõ ràng và công ty uy tín phải xếp trên tin lương thỏa thuận không rõ thông tin
        j_quality = {
            "id": 20,
            "title": "Cloud Platform Lead",
            "skills": ["AWS", "Docker", "Kubernetes"],
            "company_name": "Top Corp",
            "salary_min": 50_000_000,
            "salary_max": 80_000_000,
            "is_salary_negotiable": False,
            "is_verified": True,
            "created_at": self.now,
        }
        j_negotiable = {
            "id": 21,
            "title": "Security Analyst",
            "skills": ["Security"],
            "company_name": "Unknown Corp",
            "salary_min": None,
            "salary_max": None,
            "is_salary_negotiable": True,
            "is_verified": False,
            "created_at": self.now - timedelta(days=60),
        }

        s_quality = compute_relevance_score(j_quality)
        s_negotiable = compute_relevance_score(j_negotiable)

        self.assertGreater(s_quality, s_negotiable, "Tin minh bạch lương & uy tín phải được ưu tiên cho khách")


if __name__ == "__main__":
    unittest.main()
