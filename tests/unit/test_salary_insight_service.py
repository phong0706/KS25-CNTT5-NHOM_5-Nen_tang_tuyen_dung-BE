"""test_salary_insight_service.py
Unit tests cho logic so sánh lương:
- 0 tin cùng nhóm -> None
- 4 tin cùng nhóm (< 5) -> None
- 5 tin cùng nhóm (>= 5) -> có insight chuẩn xác
- 6 tin cùng nhóm -> tính median chuẩn xác (số chẵn)
- Tin thỏa thuận bị loại bỏ
- Chính tin đó không được tính vào mẫu
- Nhóm cấp bậc khác bị loại
- Ẩn khi |chênh lệch| < 5%
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.salary_insight_service import compute_median, evaluate_salary_insight, get_job_salary_insight


def test_compute_median():
    assert compute_median([]) == 0.0
    assert compute_median([20.0]) == 20.0
    # Số lẻ (3 số): [10, 20, 30] -> 20.0
    assert compute_median([30.0, 10.0, 20.0]) == 20.0
    # Số chẵn (4 số): [10, 20, 30, 40] -> (20 + 30)/2 = 25.0
    assert compute_median([40.0, 10.0, 20.0, 30.0]) == 25.0
    # Số chẵn (6 số): [10, 20, 25, 35, 40, 50] -> (25 + 35)/2 = 30.0
    assert compute_median([10.0, 25.0, 40.0, 20.0, 50.0, 35.0]) == 30.0


def test_evaluate_salary_insight_sample_sizes():
    # 0 tin trong nhóm mẫu -> None
    label, size = evaluate_salary_insight(25.0, [])
    assert label is None
    assert size is None

    # 4 tin trong nhóm mẫu (< 5) -> None
    peers_4 = [20.0, 22.0, 24.0, 26.0]
    label, size = evaluate_salary_insight(35.0, peers_4)
    assert label is None
    assert size == 4

    # 5 tin trong nhóm mẫu (>= 5) -> Median = 24.0
    # Lương tin này = 30.0 -> Cao hơn: (30 - 24)/24 = 25%
    peers_5 = [20.0, 22.0, 24.0, 26.0, 28.0]
    label, size = evaluate_salary_insight(30.0, peers_5)
    assert size == 5
    assert label == "So với 5 tin cùng lĩnh vực và cấp bậc: +25%"

    # Lương tin này = 18.0 -> Thấp hơn: (18 - 24)/24 = -25%
    label, size = evaluate_salary_insight(18.0, peers_5)
    assert size == 5
    assert label == "So với 5 tin cùng lĩnh vực và cấp bậc: -25%"

    # 6 tin trong nhóm mẫu -> Median([20, 22, 24, 26, 28, 30]) = (24 + 26)/2 = 25.0
    peers_6 = [20.0, 22.0, 24.0, 26.0, 28.0, 30.0]
    label, size = evaluate_salary_insight(35.0, peers_6)
    assert size == 6
    # (35 - 25)/25 = 40%
    assert label == "So với 6 tin cùng lĩnh vực và cấp bậc: +40%"

    # Chênh lệch dưới 5% (|diff| < 5%) -> Ẩn huy hiệu (None)
    label, size = evaluate_salary_insight(25.5, peers_6)
    assert size == 6
    assert label is None


def test_get_job_salary_insight_exclusions():
    job = MagicMock(id=1, category_id=1, level_id=5, salary_min=30.0, salary_max=30.0, is_salary_negotiable=False)
    
    # Nhóm có 6 tin: chính tin id=1 và 5 tin khác. Nhóm level_id=4 có 5 tin khác.
    peers_map = {
        (1, 5): [(1, 30.0), (2, 20.0), (3, 22.0), (4, 24.0), (5, 26.0), (6, 28.0)],
        (1, 4): [(7, 10.0), (8, 12.0), (9, 14.0), (10, 16.0), (11, 18.0)],
    }
    # 1. Chính tin đó bị loại trừ khỏi mẫu -> còn 5 tin
    # 2. Nhóm cấp bậc khác (level=4) không bị tính gộp -> chỉ xét (1, 5)
    label, size = get_job_salary_insight(job, peers_map)
    assert size == 5
    assert label == "So với 5 tin cùng lĩnh vực và cấp bậc: +25%"

    # 3. Tin thỏa thuận bị loại bỏ
    job_neg = MagicMock(id=2, category_id=1, level_id=5, salary_min=30.0, salary_max=30.0, is_salary_negotiable=True)
    assert get_job_salary_insight(job_neg, peers_map) == (None, None)

    # 4. Khi loại trừ chính tin đó còn lại 4 tin (< 5) -> None
    peers_map_small = {
        (1, 5): [(1, 30.0), (2, 20.0), (3, 22.0), (4, 24.0), (5, 26.0)],
    }
    label_small, size_small = get_job_salary_insight(job, peers_map_small)
    assert label_small is None
    assert size_small == 4
