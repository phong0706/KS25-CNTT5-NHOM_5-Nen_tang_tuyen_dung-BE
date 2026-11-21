"""tax_calc_service.py - Module thuần tính Thuế Thu Nhập Cá Nhân (TNCN).
Căn cứ: Văn bản hợp nhất số 112/VBHN-VPQH & Biểu thuế 5 bậc năm 2026.
Giới hạn: <= 150 dòng, không phụ thuộc DB/web framework.
"""
from typing import Any, Dict, List, Optional


DEFAULT_TAX_RULES_2026: Dict[str, Any] = {
    "personal_deduction": 15500000,
    "dependent_deduction": 6200000,
    "meal_allowance_cap": 1200000,
    "casual_labor_threshold": 5000000,
    "casual_labor_rate": 0.10,
    "non_resident_rate": 0.20,
    "base_salary": 2340000,
    "regional_minimums": {"1": 4960000, "2": 4410000, "3": 3860000, "4": 3450000},
    "insurance_rates": {"social": 0.08, "health": 0.015, "unemployment": 0.01},
    "tax_brackets": [
        {"bracket": 1, "from": 0, "to": 10000000, "threshold": 10000000, "rate": 0.05, "quick_subtract": 0, "label": "Đến 10 triệu đồng"},
        {"bracket": 2, "from": 10000000, "to": 30000000, "threshold": 30000000, "rate": 0.10, "quick_subtract": 500000, "label": "Trên 10 đến 30 triệu đồng"},
        {"bracket": 3, "from": 30000000, "to": 60000000, "threshold": 60000000, "rate": 0.20, "quick_subtract": 3500000, "label": "Trên 30 đến 60 triệu đồng"},
        {"bracket": 4, "from": 60000000, "to": 100000000, "threshold": 100000000, "rate": 0.30, "quick_subtract": 9500000, "label": "Trên 60 đến 100 triệu đồng"},
        {"bracket": 5, "from": 100000000, "to": None, "threshold": 999999999999, "rate": 0.35, "quick_subtract": 14500000, "label": "Trên 100 triệu đồng"},
    ],
}


def calculate_tax_resident_contract_ge_3m(
    total_income: float,
    rules: Optional[Dict[str, Any]] = None,
    exempt_income: float = 0.0,
    dependents: int = 0,
    insurance_salary: Optional[float] = None,
    region: str = "1",
    other_deductions: float = 0.0,
    has_insurance: bool = True,
) -> Dict[str, Any]:
    """Tính thuế TNCN cho cá nhân cư trú có HĐLĐ từ 3 tháng trở lên (Biểu lũy tiến 5 bậc)."""
    cfg = rules or DEFAULT_TAX_RULES_2026
    income = max(0.0, float(total_income or 0.0))
    exempt = max(0.0, float(exempt_income or 0.0))
    taxable_income = max(0.0, income - exempt)

    # Bảo hiểm bắt buộc
    base_sal = float(cfg.get("base_salary", 2340000))
    reg_mins = cfg.get("regional_minimums", {})
    reg_min = float(reg_mins.get(str(region), 4960000))
    ins_rates = cfg.get("insurance_rates", {"social": 0.08, "health": 0.015, "unemployment": 0.01})

    ins_sal = income if insurance_salary is None else max(0.0, float(insurance_salary))
    social_base = min(ins_sal, base_sal * 20.0) if has_insurance else 0.0
    unemp_base = min(ins_sal, reg_min * 20.0) if has_insurance else 0.0

    social_ins = round(social_base * ins_rates.get("social", 0.08))
    health_ins = round(social_base * ins_rates.get("health", 0.015))
    unemp_ins = round(unemp_base * ins_rates.get("unemployment", 0.01))
    total_insurance = social_ins + health_ins + unemp_ins

    # Các khoản giảm trừ
    personal_ded = float(cfg.get("personal_deduction", 15500000))
    dep_count = max(0, int(dependents or 0))
    dep_ded = float(cfg.get("dependent_deduction", 6200000)) * dep_count
    other_ded = max(0.0, float(other_deductions or 0.0))
    total_deductions = personal_ded + dep_ded + total_insurance + other_ded

    # Thu nhập tính thuế
    assessable_income = max(0.0, taxable_income - (personal_ded + dep_ded + total_insurance + other_ded))

    # Biểu thuế lũy tiến từng phần 5 bậc
    brackets = cfg.get("tax_brackets", DEFAULT_TAX_RULES_2026["tax_brackets"])
    pit_tax = 0
    bracket_details: List[Dict[str, Any]] = []
    rem_taxable = assessable_income
    prev_threshold = 0.0

    for idx, b in enumerate(brackets):
        thresh = float(b["threshold"])
        bracket_size = thresh - prev_threshold
        taxable_in_b = min(rem_taxable, bracket_size)
        if taxable_in_b > 0:
            tax_in_b = round(taxable_in_b * float(b["rate"]))
            pit_tax += tax_in_b
            bracket_details.append({
                "bracket": b.get("bracket", idx + 1),
                "label": b.get("label", f"Bậc {idx + 1}"),
                "from": prev_threshold,
                "to": b.get("to"),
                "rate": float(b["rate"]),
                "taxable_amount": taxable_in_b,
                "tax_amount": tax_in_b,
                "is_active": True,
            })
            rem_taxable -= taxable_in_b
        else:
            bracket_details.append({
                "bracket": b.get("bracket", idx + 1),
                "label": b.get("label", f"Bậc {idx + 1}"),
                "from": prev_threshold,
                "to": b.get("to"),
                "rate": float(b["rate"]),
                "taxable_amount": 0,
                "tax_amount": 0,
                "is_active": False,
            })
        prev_threshold = thresh

    net_income = max(0.0, income - total_insurance - pit_tax)

    return {
        "target_type": "resident_contract_ge_3m",
        "total_income": income,
        "exempt_income": exempt,
        "taxable_income": taxable_income,
        "assessable_income": assessable_income,
        "pit_tax": pit_tax,
        "net_income": net_income,
        "deductions": {
            "personal": personal_ded,
            "dependents_count": dep_count,
            "dependents_amount": dep_ded,
            "total_insurance": total_insurance,
            "insurance_details": {"social": social_ins, "health": health_ins, "unemployment": unemp_ins},
            "other": other_ded,
            "total": total_deductions,
        },
        "bracket_details": bracket_details,
        "legal_basis": "Văn bản hợp nhất số 112/VBHN-VPQH & Biểu thuế 5 bậc năm 2026",
    }


def calculate_tax_resident_casual(
    total_income: float,
    rules: Optional[Dict[str, Any]] = None,
    exempt_income: float = 0.0,
) -> Dict[str, Any]:
    """Cá nhân cư trú HĐLĐ dưới 3 tháng hoặc vãng lai: Khấu trừ 10% nếu thu nhập từ 5 triệu trở lên."""
    cfg = rules or DEFAULT_TAX_RULES_2026
    income = max(0.0, float(total_income or 0.0))
    exempt = max(0.0, float(exempt_income or 0.0))
    taxable_income = max(0.0, income - exempt)
    threshold = float(cfg.get("casual_labor_threshold", 5000000))
    rate = float(cfg.get("casual_labor_rate", 0.10))

    pit_tax = round(taxable_income * rate) if taxable_income >= threshold else 0
    net_income = max(0.0, income - pit_tax)

    return {
        "target_type": "resident_casual_or_lt_3m",
        "total_income": income,
        "exempt_income": exempt,
        "taxable_income": taxable_income,
        "assessable_income": taxable_income if taxable_income >= threshold else 0.0,
        "pit_tax": pit_tax,
        "net_income": net_income,
        "rate": rate if taxable_income >= threshold else 0.0,
        "threshold": threshold,
        "note": "Khấu trừ 10% tại nguồn trên thu nhập từ 5.000.000 đồng/lần chi trả trở lên. Không giảm trừ gia cảnh.",
        "legal_basis": "Văn bản hợp nhất số 112/VBHN-VPQH",
    }


def calculate_tax_non_resident(
    total_income: float,
    rules: Optional[Dict[str, Any]] = None,
    exempt_income: float = 0.0,
) -> Dict[str, Any]:
    """Cá nhân không cư trú: Thuế suất cố định 20% trên thu nhập chịu thuế, không giảm trừ gia cảnh."""
    cfg = rules or DEFAULT_TAX_RULES_2026
    income = max(0.0, float(total_income or 0.0))
    exempt = max(0.0, float(exempt_income or 0.0))
    taxable_income = max(0.0, income - exempt)
    rate = float(cfg.get("non_resident_rate", 0.20))
    pit_tax = round(taxable_income * rate)
    net_income = max(0.0, income - pit_tax)

    return {
        "target_type": "non_resident",
        "total_income": income,
        "exempt_income": exempt,
        "taxable_income": taxable_income,
        "assessable_income": taxable_income,
        "pit_tax": pit_tax,
        "net_income": net_income,
        "rate": rate,
        "note": "Áp dụng thuế suất 20% trên tổng thu nhập chịu thuế, không giảm trừ gia cảnh.",
        "legal_basis": "Văn bản hợp nhất số 112/VBHN-VPQH",
    }
