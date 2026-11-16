"""Unit tests cho module tính điểm phù hợp việc làm (matching.py).
Kiểm tra đầy đủ các ca biên, chia cho 0, chuẩn hóa alias, điểm luôn 0-100, sắp xếp ổn định.
"""
from datetime import datetime, timedelta
import pytest
from app.services.matching import (
    normalize_skill,
    normalize_skill_list,
    compute_level_score,
    compute_location_worktype_score,
    compute_salary_score,
    compute_job_match,
)


def test_normalize_skill_aliases():
    """Kiểm tra chuẩn hóa kỹ năng qua alias (không phân biệt hoa thường)."""
    assert normalize_skill("python") == "Python"
    assert normalize_skill("PYTHON") == "Python"
    assert normalize_skill("py") == "Python"
    assert normalize_skill("fastapi") == "FastAPI"
    assert normalize_skill("FASTAPI") == "FastAPI"
    assert normalize_skill("Fast API") == "FastAPI"
    assert normalize_skill("js") == "JavaScript"
    assert normalize_skill("k8s") == "Kubernetes"
    assert normalize_skill("   docker   ") == "Docker"
    assert normalize_skill("") == ""
    assert normalize_skill(None) == ""


def test_normalize_skill_list_duplicates():
    """Kiểm tra loại bỏ trùng lặp khi danh sách chứa nhiều biến thể của cùng một kỹ năng."""
    input_skills = ["python", "Python", "PYTHON", "FastAPI", "fastapi", "docker", "DOCKER", "k8s"]
    normalized = normalize_skill_list(input_skills)
    assert normalized == ["Python", "FastAPI", "Docker", "Kubernetes"]


def test_candidate_without_skills():
    """Ứng viên chưa cập nhật kỹ năng: matched_skills rỗng, không lỗi, điểm trong khoảng [0, 100]."""
    cand = {"skills": [], "level": "Senior", "location": "Hà Nội"}
    job = {"skills": ["Python", "FastAPI", "Docker"], "level": "Senior", "location": "Hà Nội"}
    res = compute_job_match(cand, job)
    assert res["matched_skills"] == []
    assert len(res["missing_skills"]) == 3
    assert res["skills_score"] == 0
    assert res["reason"] == "Khớp 0/3 kỹ năng"
    assert 0 <= res["match_score"] <= 100


def test_job_without_skills_no_zero_division():
    """Tin tuyển dụng không yêu cầu kỹ năng cụ thể: không chia cho 0, cho điểm tối đa kỹ năng."""
    cand = {"skills": ["Python", "FastAPI"], "level": "Senior", "location": "Hà Nội"}
    job = {"skills": [], "level": "Senior", "location": "Hà Nội"}
    res = compute_job_match(cand, job)
    assert res["skills_score"] == 60
    assert res["reason"] == "Tin không yêu cầu kỹ năng cụ thể"
    assert 0 <= res["match_score"] <= 100


def test_score_strictly_clamped_0_to_100():
    """Điểm luôn nằm trong khoảng [0, 100] cho mọi trường hợp cực biên."""
    # Khớp hoàn hảo
    cand_perfect = {
        "skills": ["Python", "FastAPI", "Docker", "MySQL"],
        "level": "Senior", "location": "Hà Nội", "work_type": "Toàn thời gian", "expected_salary": 30000000
    }
    job_perfect = {
        "skills": ["Python", "FastAPI", "Docker", "MySQL"],
        "level": "Senior", "location": "Hà Nội", "work_type": "Toàn thời gian", "salary_max": 40000000
    }
    res_max = compute_job_match(cand_perfect, job_perfect)
    assert res_max["match_score"] == 100
    assert res_max["reason"] == "Khớp 4/4 kỹ năng"

    # Lệch hoàn toàn
    cand_worst = {
        "skills": ["PHP"], "level": "Intern", "location": "Cần Thơ", "work_type": "Bán thời gian", "expected_salary": 80000000
    }
    job_worst = {
        "skills": ["Rust", "Solidity"], "level": "Lead", "location": "Đà Nẵng", "work_type": "Toàn thời gian", "salary_max": 20000000
    }
    res_min = compute_job_match(cand_worst, job_worst)
    assert 0 <= res_min["match_score"] <= 100
    assert res_min["match_score"] == 0


def test_level_scoring_logic():
    """Kiểm tra tính điểm cấp bậc."""
    assert compute_level_score("Senior", "Senior") == 15
    assert compute_level_score("Middle", "Senior") == 10  # Chênh lệch 1 bậc
    assert compute_level_score("Senior", "Junior") == 0   # Chênh lệch >= 2 bậc
    assert compute_level_score("Junior", "Tất cả") == 15  # Tin nhận mọi cấp bậc
    assert compute_level_score(None, "Senior") == 8      # Chưa rõ


def test_location_and_worktype_scoring():
    """Kiểm tra tính điểm địa điểm và hình thức làm việc."""
    # Cùng Hà Nội + Toàn thời gian
    assert compute_location_worktype_score("Hà Nội", "Toàn thời gian", "Hà Nội", "Toàn thời gian") == 15
    # Remote / Toàn quốc
    assert compute_location_worktype_score("TP. Hồ Chí Minh", "Toàn thời gian", "Toàn quốc", "Linh hoạt") == 15
    # Khác địa điểm hoàn toàn
    assert compute_location_worktype_score("Hà Nội", "Toàn thời gian", "TP. Hồ Chí Minh", "Toàn thời gian") == 5


def test_salary_scoring_logic():
    """Kiểm tra tính điểm mức lương mong muốn."""
    # Thỏa thuận
    assert compute_salary_score(30000000, 20000000, 30000000, is_negotiable=True) == 10
    # Trong dải lương
    assert compute_salary_score(25000000, 20000000, 30000000) == 10
    # Vượt nhẹ <= 20%
    assert compute_salary_score(35000000, 20000000, 30000000) == 5
    # Vượt quá > 20%
    assert compute_salary_score(45000000, 20000000, 30000000) == 0


def test_stable_sorting():
    """Kiểm tra sắp xếp ổn định: match_score giảm dần, sau đó đến published_at giảm dần, rồi id giảm dần."""
    cand = {"skills": ["Python", "FastAPI"], "level": "Senior", "location": "Hà Nội"}
    now = datetime.now()

    jobs = [
        {"id": 1, "title": "Job 1", "skills": ["Python"], "published_at": now - timedelta(days=2)},
        {"id": 2, "title": "Job 2", "skills": ["Python", "FastAPI"], "published_at": now - timedelta(days=1)},
        {"id": 3, "title": "Job 3", "skills": ["Python", "FastAPI"], "published_at": now},
        {"id": 4, "title": "Job 4", "skills": ["Java"], "published_at": now},
    ]

    evaluated = []
    for j in jobs:
        m = compute_job_match(cand, j)
        evaluated.append({**j, **m})

    # Sắp xếp ổn định
    evaluated.sort(
        key=lambda x: (x["match_score"], x.get("published_at") or datetime.min, x["id"]),
        reverse=True
    )

    # Job 3 và Job 2 cùng điểm cao nhất, Job 3 mới hơn nên đứng đầu
    assert evaluated[0]["id"] == 3
    assert evaluated[1]["id"] == 2
    assert evaluated[2]["id"] == 1
    assert evaluated[3]["id"] == 4
