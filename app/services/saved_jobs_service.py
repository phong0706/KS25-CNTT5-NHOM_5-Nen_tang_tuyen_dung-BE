"""Module tính toán thuần cho trạng thái việc làm đã lưu (saved jobs).
Không truy vấn DOM, không trực tiếp gọi database, dễ kiểm thử đơn vị.
"""
from datetime import date, datetime


def compute_is_expired(
    status: str | None,
    deadline: date | datetime | str | None,
    now: datetime | None = None,
) -> bool:
    """Xác định tin tuyển dụng đã đóng hoặc hết hạn hay chưa.

    - Nếu status khác 'published' (ví dụ: 'closed', 'draft', None) -> xem như đã hết hạn / đã đóng.
    - Nếu deadline có giá trị và nhỏ hơn thời điểm hiện tại -> đã hết hạn.
    - Ngược lại -> còn hạn.
    """
    st = (status or "").strip().lower()
    if st != "published":
        return True

    if not deadline:
        return False

    current_time = now or datetime.now()

    if isinstance(deadline, datetime):
        return deadline < current_time
    elif isinstance(deadline, date):
        return deadline < current_time.date()
    elif isinstance(deadline, str):
        try:
            # Parse ISO date string (YYYY-MM-DD or full ISO)
            clean = deadline.split("T")[0]
            d = datetime.strptime(clean, "%Y-%m-%d").date()
            return d < current_time.date()
        except ValueError:
            return False

    return False
