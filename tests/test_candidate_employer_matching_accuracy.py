import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db.session import SessionLocal
from app.services.matching import (
    compute_location_worktype_score,
    normalize_skill,
    compute_job_match,
)
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.user import User
from app.models.candidate import CandidateProfile
from app.models.application import Application

client = TestClient(app)


def test_location_matching_no_stopword_false_positive():
    """
    Test ĐỎ: 'Thành phố Hà Nội' vs 'Thành phố Hồ Chí Minh'
    Không được ăn điểm địa điểm (loc_score phải = 0, chỉ có wt_score = 5 nếu cùng toàn thời gian).
    Trước đây bị lỗi ăn 10 điểm do từ 'thành' và 'phố' trùng lặp.
    """
    score_diff_city = compute_location_worktype_score(
        cand_loc="Thành phố Hà Nội",
        cand_wt="Toàn thời gian",
        job_loc="Thành phố Hồ Chí Minh",
        job_wt="Toàn thời gian",
    )
    # Kỳ vọng: loc_score = 0, wt_score = 5 => Tổng điểm phải là 5, KHÔNG được là 15!
    assert score_diff_city == 5, f"Lỗi: Hai thành phố khác nhau nhưng nhận điểm {score_diff_city} (kỳ vọng 5)"

    # Cùng thành phố nhưng khác tiền tố hành chính: phải được 10 điểm địa điểm + 5 điểm wt = 15
    score_same_city = compute_location_worktype_score(
        cand_loc="TP. Hồ Chí Minh",
        cand_wt="Toàn thời gian",
        job_loc="Hồ Chí Minh",
        job_wt="Toàn thời gian",
    )
    assert score_same_city == 15, f"Kỳ vọng 15 điểm cho cùng TP.HCM nhưng nhận {score_same_city}"


def test_modern_skill_aliases_normalization():
    """
    Test ĐỎ: Các kỹ năng phổ biến Next.js, NestJS, React Native phải được chuẩn hóa đúng.
    """
    assert normalize_skill("nextjs") == "Next.js", f"nextjs phải thành Next.js, thực tế: {normalize_skill('nextjs')}"
    assert normalize_skill("next.js") == "Next.js"
    assert normalize_skill("nestjs") == "NestJS", f"nestjs phải thành NestJS, thực tế: {normalize_skill('nestjs')}"
    assert normalize_skill("react native") == "React Native"


def test_candidate_profile_level_evaluated_in_matching():
    """
    Test ĐỎ: compute_job_match phải dùng đúng cand['level'] khi truyền vào.
    """
    cand = {
        "skills": ["Python", "FastAPI"],
        "level": "Senior",
        "location": "Hà Nội",
    }
    job = {
        "skills": ["Python", "FastAPI"],
        "level": "Senior",
        "location": "Hà Nội",
    }
    res_senior = compute_job_match(cand, job)
    assert res_senior["level_score"] == 15, "Cùng cấp bậc Senior phải đạt 15 điểm level"

    cand_junior = {
        "skills": ["Python", "FastAPI"],
        "level": "Junior",
        "location": "Hà Nội",
    }
    res_junior = compute_job_match(cand_junior, job)
    assert res_junior["level_score"] == 0, "Junior ứng tuyển Senior phải nhận 0 điểm level"


def test_employer_applications_match_score_not_fake_60_percent():
    """
    Test ĐỎ: API danh sách đơn ứng tuyển /employer/applications
    cho ứng viên lệch hoàn toàn kỹ năng và cấp bậc KHÔNG được trả về 60% giả lập.
    """
    from app.routers.employer_applications import _calc_match_score
    # Giả sử job yêu cầu Python, FastAPI, Docker, Senior, Hà Nội
    # Ứng viên chỉ có PHP, Laravel, Junior, Cần Thơ
    cand_dict = {
        "skills": ["PHP", "Laravel"],
        "level": "Junior",
        "location": "Cần Thơ",
        "work_type": "Bán thời gian",
        "expected_salary": 80000000,
    }
    job_dict = {
        "skills": ["Python", "FastAPI", "Docker"],
        "level": "Senior",
        "location": "Hà Nội",
        "work_type": "Toàn thời gian",
        "salary_min": 20000000,
        "salary_max": 30000000,
        "is_salary_negotiable": False,
    }
    # Với pure matching, match_score = 0
    real_match = compute_job_match(cand_dict, job_dict)
    assert real_match["match_score"] == 0, f"Kỳ vọng 0 điểm khi lệch hoàn toàn, nhận {real_match['match_score']}"

    # Kiểm tra hàm _calc_match_score sau khi sửa gọi compute_job_match và trả về đúng điểm thực
    score = _calc_match_score(job_dict, cand_dict)
    assert score == 0, f"Lỗi: Lệch hoàn toàn nhưng _calc_match_score vẫn trả về {score}% (kỳ vọng 0%)"

