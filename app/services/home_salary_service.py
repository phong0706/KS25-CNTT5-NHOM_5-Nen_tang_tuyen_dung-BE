"""Module tính toán & cấu hình lương trung vị theo kỹ năng trên trang chủ.
Tuân thủ Bước 2 & techrecruit-rules: < 195 dòng, xử lý ngoại lệ biên, không phụ thuộc DB trong hàm thuần.
"""
from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


USD_EXCHANGE_RATE, USD_THRESHOLD = 25400, 1_000_000


def normalize_salary_amount(val: Optional[float]) -> Optional[float]:
    """Chuẩn hoá lương USD sang VNĐ nếu <= USD_THRESHOLD."""
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v * USD_EXCHANGE_RATE if v <= USD_THRESHOLD else v


def calculate_median_salary(salaries: List[float]) -> int:
    """Tính trung vị của mảng lương.
    Lọc bỏ giá trị <= 0. Nếu mảng rỗng trả về 0.
    Nếu lẻ lấy phần tử giữa, nếu chẵn lấy trung bình cộng 2 phần tử giữa.
    """
    valid = [float(s) for s in salaries if s is not None and s > 0]
    if not valid:
        return 0
    valid.sort()
    n = len(valid)
    if n % 2 == 1:
        return round(valid[n // 2])
    return round((valid[n // 2 - 1] + valid[n // 2]) / 2.0)


def filter_eligible_salary_jobs(jobs: List[Dict[str, Any]], now_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Lọc các tin tuyển dụng đủ điều kiện tính lương:
    - Đang mở (status == 'published')
    - Chưa bị xóa mềm (deleted_at is None)
    - Không thỏa thuận (is_salary_negotiable == False)
    - Công ty đã xác minh (is_company_verified == True)
    - Còn hạn (deadline is None hoặc deadline >= now_date)
    - Có lương công khai > 0 (tự đảo min/max nếu khoảng lương bị ngược)
    """
    check_date = now_date or date.today()
    eligible: List[Dict[str, Any]] = []

    for j in jobs:
        if j.get("status") != "published":
            continue
        if j.get("deleted_at") is not None:
            continue
        if j.get("is_salary_negotiable") is True:
            continue
        if not j.get("is_company_verified", False):
            continue

        dl = j.get("deadline")
        if dl is not None:
            if isinstance(dl, str):
                dl = date.fromisoformat(dl)
            if dl < check_date:
                continue

        min_s = normalize_salary_amount(j.get("salary_min"))
        max_s = normalize_salary_amount(j.get("salary_max"))

        if min_s is None and max_s is None:
            continue
        if min_s is not None and max_s is not None and min_s > max_s:
            min_s, max_s = max_s, min_s

        if min_s is not None and max_s is not None:
            computed = (min_s + max_s) / 2.0
        else:
            computed = min_s if min_s is not None else max_s

        if not computed or computed <= 0:
            continue

        item = dict(j)
        item["computed_salary"] = computed
        eligible.append(item)

    return eligible


def aggregate_skills_salary(
    jobs: List[Dict[str, Any]],
    min_sample: int = 5,
    max_items: int = 6,
    overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Gom nhóm mức lương theo kỹ năng, áp dụng overrides (ghim/ẩn),
    lọc min_sample và sắp xếp ổn định.
    """
    from collections import defaultdict
    overrides_map = overrides or {}
    groups: Dict[str, List[float]] = defaultdict(list)

    for j in jobs:
        sal = j.get("computed_salary")
        if not sal or sal <= 0:
            continue
        skills = j.get("skills") or []
        for s in skills:
            name = s.get("name", "") if isinstance(s, dict) else str(s)
            name = name.strip()
            if name:
                groups[name].append(float(sal))

    pinned_items: List[Dict[str, Any]] = []
    auto_items: List[Dict[str, Any]] = []

    for skill, sals in groups.items():
        ov = overrides_map.get(skill, {})
        mode = ov.get("mode", "auto")
        if mode == "hidden":
            continue

        count = len(sals)
        is_pinned = mode == "pinned"
        if not is_pinned and count < min_sample:
            continue

        med = calculate_median_salary(sals)
        val_in_tr = round(med / 1_000_000.0, 1)
        display_sal = f"{val_in_tr:.1f}".replace(".", ",") + " tr/tháng"

        info = {
            "skill": skill,
            "median_salary": med,
            "sample_count": count,
            "display_salary": display_sal,
            "is_pinned": is_pinned,
            "position": ov.get("position"),
        }
        if is_pinned:
            pinned_items.append(info)
        else:
            auto_items.append(info)

    pinned_items.sort(key=lambda x: (x["position"] if x["position"] is not None else 999, -x["median_salary"], x["skill"]))
    auto_items.sort(key=lambda x: (-x["median_salary"], -x["sample_count"], x["skill"]))

    combined = pinned_items + auto_items
    return combined[:max_items]


class SalarySettingsPayload(BaseModel):
    min_sample: int = Field(..., ge=1, le=50)
    max_items: int = Field(..., ge=1, le=12)
    version: int
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        s = v.strip() if isinstance(v, str) else ""
        if len(s) < 10:
            raise ValueError("Lý do thay đổi cấu hình bắt buộc tối thiểu 10 ký tự.")
        return s


class SkillOverrideItem(BaseModel):
    skill_id: Any
    skill_name: Optional[str] = None
    mode: str = Field(..., pattern="^(pinned|hidden|auto)$")
    position: Optional[int] = Field(None, ge=1, le=12)
