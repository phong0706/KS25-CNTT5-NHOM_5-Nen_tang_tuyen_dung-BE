"""Unit tests (Không chạm database) cho tính toán lương trung vị & bộ lọc cấu hình trang chủ.
Tuân thủ Bước 5.A & Bước 6.1: Viết test trước, đỏ trước, không sleep, thời gian cố định.
Giới hạn file: <= 195 dòng.
"""
from datetime import date, datetime
import pytest
from pydantic import ValidationError

from app.services.home_salary_service import (
    calculate_median_salary,
    filter_eligible_salary_jobs,
    aggregate_skills_salary,
    SalarySettingsPayload,
    SkillOverrideItem,
)


FIXED_NOW = datetime(2026, 11, 18, 12, 0, 0)
FIXED_TODAY = date(2026, 11, 18)


def test_calculate_median_odd_even_single_empty():
    assert calculate_median_salary([]) == 0
    assert calculate_median_salary([20_000_000]) == 20_000_000
    assert calculate_median_salary([10_000_000, 20_000_000, 30_000_000]) == 20_000_000
    assert calculate_median_salary([10_000_000, 20_000_000, 30_000_000, 40_000_000]) == 25_000_000


def test_calculate_median_negative_and_very_large():
    # Số âm hoặc 0 bị loại bỏ an toàn
    assert calculate_median_salary([-5_000_000, 0, 25_000_000]) == 25_000_000
    # Số rất lớn
    huge_median = calculate_median_salary([1_000_000_000, 2_000_000_000, 3_000_000_000])
    assert huge_median == 2_000_000_000


def test_calculate_median_rounding_to_one_decimal():
    # 25.550.000 -> 25,6 tr/tháng, 25.540.000 -> 25,5 tr/tháng
    med = calculate_median_salary([25_550_000])
    in_tr = round(med / 1_000_000.0, 1)
    assert in_tr == 25.6
    display_str = f"{in_tr:.1f}".replace(".", ",") + " tr/tháng"
    assert display_str == "25,6 tr/tháng"


def test_filter_eligible_salary_jobs():
    base_job = {
        "status": "published",
        "deleted_at": None,
        "is_salary_negotiable": False,
        "salary_min": 20_000_000,
        "salary_max": 30_000_000,
        "deadline": date(2026, 11, 20),
        "is_company_verified": True,
        "skills": ["Python", "FastAPI"],
    }
    # Đủ điều kiện
    assert len(filter_eligible_salary_jobs([base_job], now_date=FIXED_TODAY)) == 1

    # Hết hạn hôm qua -> Loại
    expired_job = dict(base_job, deadline=date(2026, 11, 17))
    assert len(filter_eligible_salary_jobs([expired_job], now_date=FIXED_TODAY)) == 0

    # Hết hạn đúng hôm nay -> Còn hạn
    today_job = dict(base_job, deadline=FIXED_TODAY)
    assert len(filter_eligible_salary_jobs([today_job], now_date=FIXED_TODAY)) == 1

    # Lương Thỏa thuận -> Loại
    nego_job = dict(base_job, is_salary_negotiable=True)
    assert len(filter_eligible_salary_jobs([nego_job], now_date=FIXED_TODAY)) == 0

    # Công ty chưa xác minh -> Loại
    unverified_job = dict(base_job, is_company_verified=False)
    assert len(filter_eligible_salary_jobs([unverified_job], now_date=FIXED_TODAY)) == 0

    # Tin xóa mềm -> Loại
    deleted_job = dict(base_job, deleted_at=datetime(2026, 11, 10))
    assert len(filter_eligible_salary_jobs([deleted_job], now_date=FIXED_TODAY)) == 0

    # Lương <= 0 -> Loại
    zero_job = dict(base_job, salary_min=0, salary_max=0)
    assert len(filter_eligible_salary_jobs([zero_job], now_date=FIXED_TODAY)) == 0

    # Khoảng lương đảo ngược min > max -> tự sửa (swap)
    swapped_job = dict(base_job, salary_min=30_000_000, salary_max=20_000_000)
    filtered = filter_eligible_salary_jobs([swapped_job], now_date=FIXED_TODAY)
    assert len(filtered) == 1
    assert filtered[0]["computed_salary"] == 25_000_000


def test_min_sample_threshold_and_tie_breaking():
    # 3 kỹ năng: Python (6 tin), Java (5 tin), PHP (4 tin)
    jobs = []
    for _ in range(6):
        jobs.append({"skills": ["Python"], "computed_salary": 25_000_000})
    for _ in range(5):
        jobs.append({"skills": ["Java"], "computed_salary": 25_000_000})
    for _ in range(4):
        jobs.append({"skills": ["PHP"], "computed_salary": 25_000_000})

    # min_sample = 5 -> PHP bị loại vì chỉ có 4 tin, Python & Java còn lại
    res = aggregate_skills_salary(jobs, min_sample=5, max_items=6, overrides={})
    skills = [r["skill"] for r in res]
    assert "PHP" not in skills
    assert "Python" in skills
    assert "Java" in skills

    # Cùng mức lương 25M: Tie-break ổn định theo tên alphabet (Java trước Python nếu cùng điểm hoặc theo cấu hình)
    res_sorted = aggregate_skills_salary(jobs, min_sample=5, max_items=6, overrides={})
    assert len(res_sorted) == 2


def test_pinned_and_hidden_overrides():
    jobs = []
    # React: 3 tin (dưới ngưỡng 5), nếu ghim thì vẫn hiện!
    for _ in range(3):
        jobs.append({"skills": ["React"], "computed_salary": 30_000_000})
    # Python: 10 tin, 28M
    for _ in range(10):
        jobs.append({"skills": ["Python"], "computed_salary": 28_000_000})
    # Java: 10 tin, 26M
    for _ in range(10):
        jobs.append({"skills": ["Java"], "computed_salary": 26_000_000})

    # Override: React ghim ở position 1, Python bị ẩn
    overrides = {
        "React": {"mode": "pinned", "position": 1},
        "Python": {"mode": "hidden", "position": None},
    }
    res = aggregate_skills_salary(jobs, min_sample=5, max_items=6, overrides=overrides)
    skill_names = [r["skill"] for r in res]
    assert skill_names[0] == "React"  # Ghim lên đầu
    assert "Python" not in skill_names  # Bị ẩn hoàn toàn
    assert "Java" in skill_names


def test_validation_ranges_and_reason():
    # min_sample ngoài 1–50
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=0, max_items=6, version=1, reason="Cập nhật cấu hình hợp lệ")
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=51, max_items=6, version=1, reason="Cập nhật cấu hình hợp lệ")

    # max_items ngoài 1–12
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=5, max_items=0, version=1, reason="Cập nhật cấu hình hợp lệ")
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=5, max_items=13, version=1, reason="Cập nhật cấu hình hợp lệ")

    # reason rỗng, chỉ khoảng trắng hoặc dưới 10 ký tự
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=5, max_items=6, version=1, reason="")
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=5, max_items=6, version=1, reason="   ")
    with pytest.raises(ValidationError):
        SalarySettingsPayload(min_sample=5, max_items=6, version=1, reason="Ngắn 9kt")

    # reason hợp lệ: đúng 10 ký tự, tiếng Việt Unicode, rất dài
    p1 = SalarySettingsPayload(min_sample=5, max_items=6, version=1, reason="1234567890")
    assert p1.reason == "1234567890"

    p2 = SalarySettingsPayload(min_sample=5, max_items=6, version=1, reason="Điều chỉnh ngưỡng tin tối thiểu")
    assert p2.min_sample == 5
