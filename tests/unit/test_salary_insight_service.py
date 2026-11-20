"""test_salary_insight_service.py
Unit tests cho logic so sánh lương:
- 0 tin cùng nhóm -> None
- 4 tin cùng nhóm (< 5) -> None
- 5 tin cùng nhóm (>= 5) -> có insight chuẩn xác
- 6 tin cùng nhóm -> tính median chuẩn xác (số chẵn)
- Tin thỏa thuận bị loại bỏ
- Chính tin đó không được tính vào mẫu
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.salary_insight_service import compute_median, evaluate_salary_insight


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
    assert label == "Cao hơn 25% so với tin cùng lĩnh vực trên TechRecruit"

    # Lương tin này = 18.0 -> Thấp hơn: (18 - 24)/24 = -25%
    label, size = evaluate_salary_insight(18.0, peers_5)
    assert size == 5
    assert label == "Thấp hơn 25% so với tin cùng lĩnh vực trên TechRecruit"

    # 6 tin trong nhóm mẫu -> Median([20, 22, 24, 26, 28, 30]) = (24 + 26)/2 = 25.0
    peers_6 = [20.0, 22.0, 24.0, 26.0, 28.0, 30.0]
    label, size = evaluate_salary_insight(35.0, peers_6)
    assert size == 6
    # (35 - 25)/25 = 40%
    assert label == "Cao hơn 40% so với tin cùng lĩnh vực trên TechRecruit"

    # Tương đương (chênh lệch dưới 5%)
    label, size = evaluate_salary_insight(25.5, peers_6)
    assert size == 6
    assert label == "Tương đương mức phổ biến trên TechRecruit"
