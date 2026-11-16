"""Router trả về quy tắc tính toán cho các công cụ (/api/tools/rules/{tool})."""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Any, Dict
import json

from app.db.session import get_db

router = APIRouter(prefix="/tools", tags=["Tools & Calculators"])

class CalcRuleResponse(BaseModel):
    tool_slug: str
    effective_from: str
    source: str
    rules: Dict[str, Any]

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
