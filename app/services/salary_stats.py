"""Module thuần tính toán phân vị mức lương và loại bỏ giá trị ngoại lai (1.5 IQR).
Không phụ thuộc DB hay web framework. Dùng cho unit test và API insights.
"""
from typing import List, Dict, Any, Optional
import math


def calculate_percentile(sorted_data: List[float], percentile: float) -> float:
    """Tính phân vị percentile (0 đến 100) theo phương pháp nội suy tuyến tính (linear interpolation)."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    if n == 1:
        return float(sorted_data[0])

    k = (percentile / 100.0) * (n - 1)
    i = math.floor(k)
    f = k - i

    if i >= n - 1:
        return float(sorted_data[-1])
    return float(sorted_data[i] + f * (sorted_data[i + 1] - sorted_data[i]))


def filter_iqr_outliers(sorted_data: List[float]) -> tuple[List[float], int]:
    """Loại bỏ các giá trị ngoại lai nằm ngoài [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
    Chỉ áp dụng lọc khi tập dữ liệu có từ 4 phần tử trở lên.
    Trả về: (danh sách đã lọc, số lượng ngoại lai đã loại)
    """
    if len(sorted_data) < 4:
        return sorted_data, 0

    q1 = calculate_percentile(sorted_data, 25)
    q3 = calculate_percentile(sorted_data, 75)
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    filtered = [x for x in sorted_data if lower_bound <= x <= upper_bound]
    outliers_removed = len(sorted_data) - len(filtered)
    return filtered, outliers_removed


def compute_salary_insights(salaries: List[float]) -> Dict[str, Any]:
    """Tính toán bộ chỉ số: min, p25, median, p75, max, sample_size.
    salaries: danh sách mức lương (VNĐ/tháng).
    """
    cleaned = [float(s) for s in salaries if s is not None and s > 0]
    total_samples = len(cleaned)

    if total_samples == 0:
        return {
            "sample_size": 0,
            "min": 0,
            "p25": 0,
            "median": 0,
            "p75": 0,
            "max": 0,
            "outliers_removed": 0,
            "is_sufficient": False,
        }

    cleaned.sort()
    filtered_data, outliers_count = filter_iqr_outliers(cleaned)
    final_data = filtered_data if filtered_data else cleaned

    p25 = round(calculate_percentile(final_data, 25))
    median = round(calculate_percentile(final_data, 50))
    p75 = round(calculate_percentile(final_data, 75))
    min_val = round(final_data[0])
    max_val = round(final_data[-1])

    return {
        "sample_size": total_samples,
        "effective_sample_size": len(final_data),
        "min": min_val,
        "p25": p25,
        "median": median,
        "p75": p75,
        "max": max_val,
        "outliers_removed": outliers_count,
        "is_sufficient": total_samples >= 5,
    }

