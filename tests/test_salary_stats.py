import pytest
from app.services.salary_stats import (
    calculate_percentile,
    filter_iqr_outliers,
    compute_salary_insights,
)


def test_percentile_empty():
    assert calculate_percentile([], 50) == 0.0


def test_percentile_single_element():
    assert calculate_percentile([15000000.0], 25) == 15000000.0
    assert calculate_percentile([15000000.0], 50) == 15000000.0
    assert calculate_percentile([15000000.0], 75) == 15000000.0


def test_percentile_two_elements():
    data = [10000000.0, 20000000.0]
    assert calculate_percentile(data, 0) == 10000000.0
    assert calculate_percentile(data, 50) == 15000000.0
    assert calculate_percentile(data, 100) == 20000000.0


def test_percentile_odd_count():
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calculate_percentile(data, 50) == 30.0
    assert calculate_percentile(data, 25) == 20.0
    assert calculate_percentile(data, 75) == 40.0


def test_percentile_even_count():
    data = [10.0, 20.0, 30.0, 40.0]
    # k = 0.5 * 3 = 1.5 -> data[1] + 0.5*(data[2]-data[1]) = 20 + 5 = 25.0
    assert calculate_percentile(data, 50) == 25.0


def test_percentile_identical_values():
    data = [20000000.0, 20000000.0, 20000000.0, 20000000.0, 20000000.0]
    assert calculate_percentile(data, 25) == 20000000.0
    assert calculate_percentile(data, 50) == 20000000.0
    assert calculate_percentile(data, 75) == 20000000.0


def test_iqr_outliers_filter():
    # 10, 11, 12, 13, 14, 15, 100 (100 là ngoại lai cực lớn)
    data = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 100.0]
    filtered, removed = filter_iqr_outliers(data)
    assert removed == 1
    assert 100.0 not in filtered
    assert len(filtered) == 6


def test_compute_salary_insights_insufficient():
    res = compute_salary_insights([15000000, 20000000, 25000000])
    assert res["sample_size"] == 3
    assert res["is_sufficient"] is False


def test_compute_salary_insights_sufficient_5_samples():
    salaries = [15000000, 20000000, 25000000, 30000000, 40000000]
    res = compute_salary_insights(salaries)
    assert res["sample_size"] == 5
    assert res["is_sufficient"] is True
    assert res["min"] == 15000000
    assert res["median"] == 25000000
    assert res["max"] == 40000000
    assert res["p25"] == 20000000
    assert res["p75"] == 30000000

