"""Unit tests cho Bước 4 - Lộ trình sự nghiệp:
1. Tính coverage đúng: tổng w kỹ năng ứng viên có / tổng w của vai trò.
2. Gap sắp đúng thứ tự: các kỹ năng thiếu sắp giảm dần theo w, rồi theo bảng chữ cái.
3. Bỏ vai trò dưới 5 tin: sample_size < 5 -> is_sufficient = False (insufficient_data), không sinh trọng số giả.
4. Kỹ năng viết hoa/thường và viết khác nhau (alias) được chuẩn hóa về cùng một giá trị.
"""
from pathlib import Path
import sys
from dotenv import load_dotenv

load_dotenv(Path(r"e:\THỰC TẬP NHÓM 5 RIKKEILAB\base\backend\.env"))
sys.path.insert(0, str(Path(r"e:\THỰC TẬP NHÓM 5 RIKKEILAB\base\backend")))

from app.db.session import Base, SessionLocal, engine
from app.services.career_path_service import (
    compute_role_weights_pure,
    evaluate_candidate_against_role,
    refresh_career_weights_in_db,
)
from app.services.matching import normalize_skill_list


def test_skill_normalization_case_and_aliases():
    raw_inputs = ["python", "PYTHON", "py", "Python3", "reactjs", "React.js", "REACT", "k8s", "Kubernetes", "fast api"]
    normalized = normalize_skill_list(raw_inputs)
    assert normalized == ["Python", "React", "Kubernetes", "FastAPI"], f"Unexpected normalized list: {normalized}"


def test_skip_roles_under_5_jobs():
    sample_jobs = [
        {
            "family_slug": "backend",
            "family_name": "Backend & API",
            "level_slug": "junior",
            "level_name": "Junior",
            "level_order": 3,
            "skills": ["Python", "Docker"],
            "salary_min": 15,
            "salary_max": 20,
            "is_salary_negotiable": False,
        }
        for _ in range(4)  # Chỉ có 4 tin (< 5)
    ] + [
        {
            "family_slug": "backend",
            "family_name": "Backend & API",
            "level_slug": "middle",
            "level_name": "Middle",
            "level_order": 4,
            "skills": ["Python", "Docker", "PostgreSQL"] if i < 3 else ["Python", "Redis"],
            "salary_min": 25,
            "salary_max": 35,
            "is_salary_negotiable": False,
        }
        for i in range(5)  # Đủ 5 tin (>= 5)
    ]

    res = compute_role_weights_pure(sample_jobs, min_sample=5)
    assert res["backend:junior"]["is_sufficient"] is False
    assert res["backend:junior"]["sample_size"] == 4
    assert res["backend:junior"]["skills"] == []

    assert res["backend:middle"]["is_sufficient"] is True
    assert res["backend:middle"]["sample_size"] == 5
    assert res["backend:middle"]["salary_median"] == 30


def test_coverage_calculation_and_gap_ordering():
    role_stat = {
        "role_slug": "backend:senior",
        "role_name": "Senior Backend & API",
        "family_slug": "backend",
        "family_name": "Backend & API",
        "level_slug": "senior",
        "level_name": "Senior",
        "level_order": 5,
        "sample_size": 5,
        "salary_sample_size": 5,
        "salary_median": 42,
        "is_sufficient": True,
        "data_as_of": "2026-11-18",
    }
    # Tổng w = 0.8 + 0.6 + 0.4 + 0.2 = 2.0
    role_weights = [
        {"skill_name": "Python", "weight": 0.8, "job_count": 4, "total_role_jobs": 5},
        {"skill_name": "Docker", "weight": 0.6, "job_count": 3, "total_role_jobs": 5},
        {"skill_name": "Kubernetes", "weight": 0.4, "job_count": 2, "total_role_jobs": 5},
        {"skill_name": "GraphQL", "weight": 0.2, "job_count": 1, "total_role_jobs": 5},
    ]
    # Ứng viên có "py" (Python, w=0.8) và "GRAPHQL" (GraphQL, w=0.2) -> matched_w = 1.0 / 2.0 = 0.5 (50%, 2/4 kỹ năng)
    evaluated = evaluate_candidate_against_role(["py", "GRAPHQL"], role_stat, role_weights)
    assert evaluated["coverage"] == 0.5
    assert evaluated["coverage_percent"] == 50
    assert evaluated["matched_skill_count"] == 2
    assert evaluated["total_skill_count"] == 4
    assert evaluated["coverage_label"] == "2/4 kỹ năng"

    # Kỹ năng thiếu phải là Docker (w=0.6) rồi tới Kubernetes (w=0.4)
    missing = evaluated["missing_skills"]
    assert [m["name"] for m in missing] == ["Docker", "Kubernetes"]
    assert [m["weight"] for m in missing] == [0.6, 0.4]


def test_db_refresh_and_real_role_counts():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        summary = refresh_career_weights_in_db(db)
        print("DB Refresh Summary:", summary)
        assert summary["sufficient_roles"] >= 4
        assert summary["insufficient_roles"] >= 1


if __name__ == "__main__":
    test_skill_normalization_case_and_aliases()
    print("[PASS] test_skill_normalization_case_and_aliases")
    test_skip_roles_under_5_jobs()
    print("[PASS] test_skip_roles_under_5_jobs")
    test_coverage_calculation_and_gap_ordering()
    print("[PASS] test_coverage_calculation_and_gap_ordering")
    test_db_refresh_and_real_role_counts()
    print("[PASS] test_db_refresh_and_real_role_counts")
