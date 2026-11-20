"""Router trả về quy tắc tính toán cho các công cụ (/api/tools/rules/{tool})."""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Any, Dict, Optional
import json

from app.db.session import get_db
from app.services.tax_calc_service import (
    calculate_tax_resident_contract_ge_3m,
    calculate_tax_resident_casual,
    calculate_tax_non_resident,
)

router = APIRouter(prefix="/tools", tags=["Tools & Calculators"])

class CalcRuleResponse(BaseModel):
    tool_slug: str
    effective_from: str
    source: str
    rules: Dict[str, Any]

class TaxCalculationRequest(BaseModel):
    target_type: str = "resident_contract_ge_3m"  # resident_contract_ge_3m | resident_casual_or_lt_3m | non_resident
    total_income: float = 0.0
    exempt_income: float = 0.0
    dependents: int = 0
    insurance_salary: Optional[float] = None
    region: str = "1"
    other_deductions: float = 0.0
    has_insurance: bool = True

@router.get("/rules/{tool}", response_model=CalcRuleResponse, summary="Lấy quy tắc tính toán theo công cụ")
def get_tool_rules(tool: str, response: Response, db: Session = Depends(get_db)):
    """Trả về mức thuế, tỷ lệ bảo hiểm, giảm trừ gia cảnh... từ bảng calc_rules."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    stmt = text("""
        SELECT tool_slug, effective_from, source, rules_json 
        FROM calc_rules 
        WHERE tool_slug = :tool 
        ORDER BY effective_from DESC 
        LIMIT 1
    """)
    row = db.execute(stmt, {"tool": tool}).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc tính toán cho công cụ '{tool}'."
        )

    rules_data = row.rules_json
    if isinstance(rules_data, str):
        try:
            rules_data = json.loads(rules_data)
        except Exception:
            rules_data = {}

    return CalcRuleResponse(
        tool_slug=row.tool_slug,
        effective_from=str(row.effective_from),
        source=row.source,
        rules=rules_data or {}
    )


@router.post("/calculate/tax", summary="Tính thuế thu nhập cá nhân (TNCN) theo quy định")
def calculate_tax_api(payload: TaxCalculationRequest, db: Session = Depends(get_db)):
    """Tính toán thuế TNCN cho cá nhân cư trú (5 bậc hoặc vãng lai) và không cư trú."""
    stmt = text("SELECT rules_json FROM calc_rules WHERE tool_slug = 'tax' ORDER BY effective_from DESC LIMIT 1")
    row = db.execute(stmt).fetchone()
    rules_data = None
    if row and row[0]:
        try:
            rules_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception:
            pass

    t_type = payload.target_type
    if t_type == "resident_casual_or_lt_3m":
        return calculate_tax_resident_casual(
            total_income=payload.total_income,
            rules=rules_data,
            exempt_income=payload.exempt_income,
        )
    elif t_type == "non_resident":
        return calculate_tax_non_resident(
            total_income=payload.total_income,
            rules=rules_data,
            exempt_income=payload.exempt_income,
        )
    else:
        return calculate_tax_resident_contract_ge_3m(
            total_income=payload.total_income,
            rules=rules_data,
            exempt_income=payload.exempt_income,
            dependents=payload.dependents,
            insurance_salary=payload.insurance_salary,
            region=payload.region,
            other_deductions=payload.other_deductions,
            has_insurance=payload.has_insurance,
        )
