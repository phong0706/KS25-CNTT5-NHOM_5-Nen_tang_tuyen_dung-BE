"""Unit & API Tests cho Bộ tính Thuế Thu Nhập Cá Nhân (TNCN).
Căn cứ: Văn bản hợp nhất số 112/VBHN-VPQH & Biểu thuế 5 bậc năm 2026.
Giới hạn: <= 180 dòng.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.tax_calc_service import (
    calculate_tax_resident_contract_ge_3m,
    calculate_tax_resident_casual,
    calculate_tax_non_resident,
    DEFAULT_TAX_RULES_2026,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_user_prompt_example_match():
    """Ví dụ đề bài: Gross 30M, BH 10.5% (3.15M), 1 người phụ thuộc -> TNTT = 5.150.000đ -> Thuế = 257.500đ."""
    res = calculate_tax_resident_contract_ge_3m(
        total_income=30_000_000,
        dependents=1,
        insurance_salary=30_000_000,
        has_insurance=True,
    )
    assert res["total_income"] == 30_000_000
    assert res["deductions"]["personal"] == 15_500_000
    assert res["deductions"]["dependents_amount"] == 6_200_000
    assert res["deductions"]["total_insurance"] == 3_150_000
    # TNTT = 30.000.000 - 3.150.000 - 15.500.000 - 6.200.000 = 5.150.000
    assert res["assessable_income"] == 5_150_000
    # Bậc 1: 5.150.000 * 5% = 257.500
    assert res["pit_tax"] == 257_500
    assert res["net_income"] == 30_000_000 - 3_150_000 - 257_500


def test_below_tax_threshold():
    """Thu nhập dưới ngưỡng giảm trừ bản thân (15.5M) -> Không phải nộp thuế."""
    res = calculate_tax_resident_contract_ge_3m(total_income=14_000_000, dependents=0)
    assert res["assessable_income"] == 0
    assert res["pit_tax"] == 0
    assert res["net_income"] > 0


def test_progressive_brackets_1_to_5():
    """Kiểm tra tính thuế chính xác theo từng bậc 1 đến 5 (lũy tiến từng phần & cách tính nhanh)."""
    # Bậc 1: TNTT = 10.000.000đ -> 10M * 5% = 500.000đ
    # Để TNTT = 10M: thu nhập = 10M + 15.5M (không tính bảo hiểm)
    r1 = calculate_tax_resident_contract_ge_3m(total_income=25_500_000, dependents=0, has_insurance=False)
    assert r1["assessable_income"] == 10_000_000
    assert r1["pit_tax"] == 500_000

    # Bậc 2: TNTT = 20.000.000đ -> 20M * 10% - 500.000 = 1.500.000đ
    r2 = calculate_tax_resident_contract_ge_3m(total_income=35_500_000, dependents=0, has_insurance=False)
    assert r2["assessable_income"] == 20_000_000
    assert r2["pit_tax"] == 1_500_000

    # Bậc 3: TNTT = 50.000.000đ -> 50M * 20% - 3.500.000 = 6.500.000đ
    r3 = calculate_tax_resident_contract_ge_3m(total_income=65_500_000, dependents=0, has_insurance=False)
    assert r3["assessable_income"] == 50_000_000
    assert r3["pit_tax"] == 6_500_000

    # Bậc 4: TNTT = 80.000.000đ -> 80M * 30% - 9.500.000 = 14.500.000đ
    r4 = calculate_tax_resident_contract_ge_3m(total_income=95_500_000, dependents=0, has_insurance=False)
    assert r4["assessable_income"] == 80_000_000
    assert r4["pit_tax"] == 14_500_000

    # Bậc 5: TNTT = 150.000.000đ -> 150M * 35% - 14.500.000 = 38.000.000đ
    r5 = calculate_tax_resident_contract_ge_3m(total_income=165_500_000, dependents=0, has_insurance=False)
    assert r5["assessable_income"] == 150_000_000
    assert r5["pit_tax"] == 38_000_000


def test_bracket_boundaries():
    """Kiểm tra chính xác tại các điểm mốc: 10M, 30M, 60M, 100M."""
    # Mốc 30M: 30M * 10% - 500k = 2.500.000đ
    r_30 = calculate_tax_resident_contract_ge_3m(total_income=45_500_000, dependents=0, has_insurance=False)
    assert r_30["assessable_income"] == 30_000_000
    assert r_30["pit_tax"] == 2_500_000

    # Mốc 60M: 60M * 20% - 3.5M = 8.500.000đ
    r_60 = calculate_tax_resident_contract_ge_3m(total_income=75_500_000, dependents=0, has_insurance=False)
    assert r_60["assessable_income"] == 60_000_000
    assert r_60["pit_tax"] == 8_500_000

    # Mốc 100M: 100M * 30% - 9.5M = 20.500.000đ
    r_100 = calculate_tax_resident_contract_ge_3m(total_income=115_500_000, dependents=0, has_insurance=False)
    assert r_100["assessable_income"] == 100_000_000
    assert r_100["pit_tax"] == 20_500_000


def test_exempt_meal_allowance():
    """Khoản miễn thuế ăn ca (1.2M) giảm thu nhập chịu thuế."""
    res = calculate_tax_resident_contract_ge_3m(
        total_income=30_000_000,
        exempt_income=1_200_000,
        dependents=1,
        insurance_salary=30_000_000,
    )
    assert res["taxable_income"] == 28_800_000
    # TNTT = 28.8M - 3.15M - 15.5M - 6.2M = 3.950.000đ
    assert res["assessable_income"] == 3_950_000
    assert res["pit_tax"] == round(3_950_000 * 0.05)


def test_resident_casual_under_and_over_5m():
    """HĐLĐ dưới 3 tháng / vãng lai: < 5M thuế = 0, >= 5M khấu trừ 10%."""
    r_low = calculate_tax_resident_casual(total_income=4_999_999)
    assert r_low["pit_tax"] == 0
    assert r_low["net_income"] == 4_999_999

    r_exact = calculate_tax_resident_casual(total_income=5_000_000)
    assert r_exact["pit_tax"] == 500_000
    assert r_exact["net_income"] == 4_500_000

    r_high = calculate_tax_resident_casual(total_income=12_000_000, exempt_income=2_000_000)
    # Thu nhập chịu thuế = 10M >= 5M -> thuế 10% = 1.000.000đ
    assert r_high["taxable_income"] == 10_000_000
    assert r_high["pit_tax"] == 1_000_000
    assert r_high["net_income"] == 11_000_000


def test_non_resident_flat_20_percent():
    """Cá nhân không cư trú: thuế suất phẳng 20% trên thu nhập chịu thuế."""
    res = calculate_tax_non_resident(total_income=25_000_000, exempt_income=1_000_000)
    assert res["taxable_income"] == 24_000_000
    assert res["pit_tax"] == round(24_000_000 * 0.20)
    assert res["net_income"] == 25_000_000 - 4_800_000


def test_api_endpoints(client):
    """Kiểm tra API GET /api/tools/rules/tax và POST /api/tools/calculate/tax."""
    # 1. Rules
    r_rules = client.get("/api/tools/rules/tax")
    assert r_rules.status_code == 200
    data = r_rules.json()
    assert data["tool_slug"] == "tax"
    assert "112/VBHN-VPQH" in data["source"]
    assert data["rules"]["personal_deduction"] == 15_500_000
    assert data["rules"]["dependent_deduction"] == 6_200_000

    # 2. Calculate API (resident >= 3m)
    r_calc = client.post("/api/tools/calculate/tax", json={
        "target_type": "resident_contract_ge_3m",
        "total_income": 30_000_000,
        "dependents": 1,
        "insurance_salary": 30_000_000,
        "has_insurance": True,
    })
    assert r_calc.status_code == 200
    calc_res = r_calc.json()
    assert calc_res["pit_tax"] == 257_500
    assert calc_res["assessable_income"] == 5_150_000

    # 3. Calculate API (casual < 3m)
    r_casual = client.post("/api/tools/calculate/tax", json={
        "target_type": "resident_casual_or_lt_3m",
        "total_income": 8_000_000,
    })
    assert r_casual.status_code == 200
    assert r_casual.json()["pit_tax"] == 800_000

    # 4. Calculate API (non-resident)
    r_non = client.post("/api/tools/calculate/tax", json={
        "target_type": "non_resident",
        "total_income": 10_000_000,
    })
    assert r_non.status_code == 200
    assert r_non.json()["pit_tax"] == 2_000_000
