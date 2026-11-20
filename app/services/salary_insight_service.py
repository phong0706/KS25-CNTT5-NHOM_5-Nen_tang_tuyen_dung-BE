"""salary_insight_service.py
Dịch vụ tính toán huy hiệu so sánh lương (Salary Insight) theo chuẩn techrecruit-rules:
- Chỉ trả khi có >= 5 tin ĐANG TUYỂN, CÓ KHAI LƯƠNG, cùng lĩnh vực VÀ cùng cấp bậc (chính tin đó không tính).
- So sánh chuẩn xác với TRUNG VỊ (median), loại bỏ tin thỏa thuận.
- Trả kèm sample_size.
- Giới hạn: <= 200 dòng.
"""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job


def compute_median(salaries: List[float]) -> float:
    """Tính trung vị (median) từ danh sách mức lương."""
    if not salaries:
        return 0.0
    s_sorted = sorted(salaries)
    n = len(s_sorted)
    mid = n // 2
    if n % 2 == 1:
        return float(s_sorted[mid])
    return float((s_sorted[mid - 1] + s_sorted[mid]) / 2.0)


def evaluate_salary_insight(
    job_salary: float,
    peer_salaries: List[float],
    min_sample_size: int = 5,
) -> Tuple[Optional[str], Optional[int]]:
    """Đánh giá salary_insight dựa trên lương tin đang xét và danh sách lương cùng nhóm.
    
    Returns:
        (insight_label, sample_size)
    """
    sample_size = len(peer_salaries)
    if sample_size < min_sample_size or job_salary <= 0:
        return None, sample_size if sample_size > 0 else None

    med = compute_median(peer_salaries)
    if med <= 0:
        return None, sample_size

    diff_pct = int(round(((job_salary - med) / med) * 100))
    if diff_pct >= 5:
        return f"Cao hơn {diff_pct}% so với tin cùng lĩnh vực trên TechRecruit", sample_size
    elif diff_pct <= -5:
        return f"Thấp hơn {abs(diff_pct)}% so với tin cùng lĩnh vực trên TechRecruit", sample_size
    return "Tương đương mức phổ biến trên TechRecruit", sample_size


def fetch_peers_salaries_map(db: Session, today: Optional[date] = None) -> Dict[Tuple[int, int], List[Tuple[int, float]]]:
    """Lấy danh sách (job_id, salary) cho toàn bộ tin đang tuyển công khai nhóm theo (category_id, level_id).
    
    Quy tắc lọc:
    - category_id is not null và level_id is not null
    - status == 'published'
    - is_salary_negotiable == False và (salary_min is not null or salary_max is not null)
    - Company.is_visible == True
    - deadline >= today hoặc deadline is null
    """
    cur_date = today or date.today()
    stmt = (
        select(Job.id, Job.category_id, Job.level_id, Job.salary_min, Job.salary_max)
        .join(Company, Job.company_id == Company.id)
        .where(
            Job.category_id.is_not(None),
            Job.level_id.is_not(None),
            Job.status == "published",
            Job.is_salary_negotiable == False,  # noqa: E712
            (Job.salary_min.is_not(None) | Job.salary_max.is_not(None)),
            Company.is_visible == True,  # noqa: E712
            or_(Job.deadline.is_(None), Job.deadline >= cur_date),
        )
    )
    rows = db.execute(stmt).all()
    group_map: Dict[Tuple[int, int], List[Tuple[int, float]]] = {}
    for r in rows:
        key = (int(r.category_id), int(r.level_id))
        s_min = float(r.salary_min) if r.salary_min is not None else float(r.salary_max)
        s_max = float(r.salary_max) if r.salary_max is not None else float(r.salary_min)
        avg_sal = (s_min + s_max) / 2.0
        if avg_sal > 0:
            group_map.setdefault(key, []).append((int(r.id), avg_sal))
    return group_map


def get_job_salary_insight(
    job: Any,
    peers_map: Dict[Tuple[int, int], List[Tuple[int, float]]],
) -> Tuple[Optional[str], Optional[int]]:
    """Tính salary insight cho 1 tin cụ thể từ bản đồ peers đã fetch sẵn."""
    if not job.category_id or not job.level_id or getattr(job, "is_salary_negotiable", False):
        return None, None

    s_min = getattr(job, "salary_min", None)
    s_max = getattr(job, "salary_max", None)
    if s_min is None and s_max is None:
        return None, None

    job_sal = (float(s_min or s_max) + float(s_max or s_min)) / 2.0
    if job_sal <= 0:
        return None, None

    key = (int(job.category_id), int(job.level_id))
    all_in_group = peers_map.get(key, [])
    # Loại trừ chính tin đó khỏi tập mẫu so sánh
    peer_sals = [sal for jid, sal in all_in_group if jid != job.id]

    return evaluate_salary_insight(job_sal, peer_sals, min_sample_size=5)
