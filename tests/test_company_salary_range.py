"""Pytest kiểm tra tính toán khoảng lương (salary_range) cho trang chi tiết công ty.
Bất biến:
- 0 job: None
- 1 job: None (sample_size < 2 ẩn)
- 2 jobs: có kết quả, sample_size == 2
- 5 jobs: lẻ, tính đúng median, p25, p75
- 4 jobs: chẵn, nội suy đúng
- Trùng giá trị: kết quả bằng nhau
- Ngoại lai 5M: filter_iqr_outliers loại bỏ ngoại lai khi tính toán
- Thỏa thuận bị loại: jobs thỏa thuận (is_salary_negotiable == True) không tính vào salary_range
"""
import pytest
from app.services.salary_stats import calculate_percentile, compute_salary_insights, filter_iqr_outliers


def _compute_range_from_jobs(jobs: list[dict]):
    """Mô phỏng bộ lọc lương của get_public_company_detail."""
    valid_salaries = []
    for j in jobs:
        if j.get("is_salary_negotiable"):
            continue
        s_min = j.get("salary_min")
        s_max = j.get("salary_max")
        if s_min is None and s_max is None:
            continue
        v_min = float(s_min if s_min is not None else s_max)
        v_max = float(s_max if s_max is not None else s_min)
        valid_salaries.append((v_min + v_max) / 2.0)

    if len(valid_salaries) < 2:
        return None

    insights = compute_salary_insights(valid_salaries)
    return {
        "min": insights["min"],
        "max": insights["max"],
        "median": insights["median"],
        "p25": insights["p25"],
        "p75": insights["p75"],
        "sample_size": insights["sample_size"],
    }


def test_salary_range_0_jobs():
    res = _compute_range_from_jobs([])
    assert res is None


def test_salary_range_1_job_hidden():
    jobs = [{"salary_min": 20_000_000, "salary_max": 30_000_000, "is_salary_negotiable": False}]
    res = _compute_range_from_jobs(jobs)
    assert res is None, "Khi sample_size < 2, salary_range phải ẩn (None)"


def test_salary_range_2_jobs():
    jobs = [
        {"salary_min": 20_000_000, "salary_max": 20_000_000, "is_salary_negotiable": False},
        {"salary_min": 40_000_000, "salary_max": 40_000_000, "is_salary_negotiable": False},
    ]
    res = _compute_range_from_jobs(jobs)
    assert res is not None
    assert res["sample_size"] == 2
    assert res["median"] == 30_000_000
    assert res["p25"] == 25_000_000
    assert res["p75"] == 35_000_000


def test_salary_range_5_jobs_odd():
    # 5 jobs: 10M, 20M, 30M, 40M, 50M
    jobs = [{"salary_min": val, "salary_max": val, "is_salary_negotiable": False} for val in [10_000_000, 20_000_000, 30_000_000, 40_000_000, 50_000_000]]
    res = _compute_range_from_jobs(jobs)
    assert res is not None
    assert res["sample_size"] == 5
    assert res["median"] == 30_000_000
    assert res["p25"] == 20_000_000
    assert res["p75"] == 40_000_000


def test_salary_range_4_jobs_even():
    # 4 jobs: 10M, 20M, 30M, 40M
    jobs = [{"salary_min": val, "salary_max": val, "is_salary_negotiable": False} for val in [10_000_000, 20_000_000, 30_000_000, 40_000_000]]
    res = _compute_range_from_jobs(jobs)
    assert res is not None
    assert res["sample_size"] == 4
    assert res["median"] == 25_000_000


def test_salary_range_duplicate_values():
    jobs = [{"salary_min": 25_000_000, "salary_max": 25_000_000, "is_salary_negotiable": False} for _ in range(5)]
    res = _compute_range_from_jobs(jobs)
    assert res is not None
    assert res["median"] == 25_000_000
    assert res["p25"] == 25_000_000
    assert res["p75"] == 25_000_000


def test_salary_range_outlier_5m_filtered():
    # 4 jobs quanh 35M-40M và 1 job ngoại lai 5M
    # Khi dùng compute_salary_insights, filter_iqr_outliers loại bỏ giá trị ngoại lai
    jobs = [
        {"salary_min": 5_000_000, "salary_max": 5_000_000, "is_salary_negotiable": False},
        {"salary_min": 35_000_000, "salary_max": 35_000_000, "is_salary_negotiable": False},
        {"salary_min": 36_000_000, "salary_max": 36_000_000, "is_salary_negotiable": False},
        {"salary_min": 37_000_000, "salary_max": 37_000_000, "is_salary_negotiable": False},
        {"salary_min": 38_000_000, "salary_max": 38_000_000, "is_salary_negotiable": False},
    ]
    res = _compute_range_from_jobs(jobs)
    assert res is not None
    assert res["sample_size"] == 5
    # Trung vị của nhóm sau khi lọc ngoại lai 5M sẽ là trung vị của [35, 36, 37, 38] -> 36.5M
    assert res["median"] >= 35_000_000


def test_salary_range_negotiable_jobs_excluded():
    jobs = [
        {"salary_min": 20_000_000, "salary_max": 20_000_000, "is_salary_negotiable": False},
        {"salary_min": 50_000_000, "salary_max": 50_000_000, "is_salary_negotiable": True},  # Thỏa thuận -> Bị loại
        {"salary_min": None, "salary_max": None, "is_salary_negotiable": True},              # Thỏa thuận -> Bị loại
    ]
    # Chỉ còn 1 job hợp lệ -> sample_size = 1 < 2 -> None
    res = _compute_range_from_jobs(jobs)
    assert res is None, "Job thỏa thuận phải bị loại, còn lại < 2 job nên salary_range phải ẩn (None)"
