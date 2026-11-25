"""skills_normalizer.py
Chuẩn hóa danh sách kỹ năng cho tin tuyển dụng (Job Skills Normalizer).
Tuân thủ techrecruit-rules: <= 200 dòng, không phụ thuộc nặng, xử lý triệt để chuỗi/mảng/None.
"""
import re
from typing import Any, List

SKILL_DELIMITERS_REGEX = re.compile(r"[,;|/\n\r\t]+")
STRIP_CHARS = " \t\n\r\"'#*•-`"


def normalize_skills(val: Any, max_skills: int = 8) -> List[str]:
    """Chuẩn hóa dữ liệu kỹ năng thành list[str] sạch sẽ, tối đa max_skills, không trùng.
    
    Quy tắc:
    - Nếu val là None, bool, rỗng -> []
    - Nếu val là str -> tách theo [,;|/\\n], loại bỏ khoảng trắng và ký tự lạ
    - Nếu val là list/tuple/set -> ép từng phần tử thành chuỗi, loại bỏ rỗng
    - Giữ thứ tự xuất hiện ban đầu, không trùng lặp (case-insensitive deduplication)
    - Cắt tối đa max_skills kỹ năng (mặc định 8)
    """
    if val is None or isinstance(val, bool):
        return []

    raw_items: List[str] = []
    if isinstance(val, str):
        # Tách chuỗi theo dấu phân cách
        parts = SKILL_DELIMITERS_REGEX.split(val)
        raw_items = [p for p in parts if p.strip(STRIP_CHARS)]
    elif isinstance(val, (list, tuple, set)):
        for item in val:
            if item is None or isinstance(item, bool):
                continue
            if isinstance(item, str):
                parts = SKILL_DELIMITERS_REGEX.split(item)
                raw_items.extend(p for p in parts if p.strip(STRIP_CHARS))
            else:
                s = str(item).strip(STRIP_CHARS)
                if s:
                    raw_items.append(s)
    else:
        s = str(val).strip(STRIP_CHARS)
        if s:
            raw_items = [s]

    clean_skills: List[str] = []
    seen = set()

    for item in raw_items:
        clean = item.strip(STRIP_CHARS)
        # Giới hạn độ dài tối đa mỗi kỹ năng (tối đa 40 ký tự)
        if len(clean) > 40:
            clean = clean[:40].strip(STRIP_CHARS)
        if not clean:
            continue
        lower_key = clean.lower()
        if lower_key not in seen:
            seen.add(lower_key)
            clean_skills.append(clean)
            if len(clean_skills) >= max_skills:
                break

    return clean_skills
