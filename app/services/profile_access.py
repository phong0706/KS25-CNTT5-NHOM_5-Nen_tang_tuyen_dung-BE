"""Module thuần xác định ma trận quyền truy cập hồ sơ ứng viên (SEC-PROFILE-01).
Tuân thủ techrecruit-rules: logic thuần túy, không phụ thuộc framework, < 180 dòng.
"""
from collections import defaultdict, deque
import threading
import time
import urllib.parse


def safe_url(url: str | None) -> str | None:
    """Sanitize URL an toàn: chỉ cho phép http / https, loại bỏ XSS / javascript / data."""
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            # Chặn ký tự điều khiển hoặc HTML tags
            if any(c in url for c in ("\r", "\n", "\t", "<", ">", '"', "'")):
                return None
            return url
    except Exception:
        pass
    return None


def resolve_profile_access(viewer, candidate, applications: list | None = None) -> str:
    """Xác định quyền truy cập hồ sơ ứng viên: trả về 'full' | 'public' | 'none'.
    
    Quy tắc:
    - full: ứng viên có ÍT NHẤT MỘT hồ sơ ứng tuyển, chưa rút, vào tin do employer sở hữu;
            hoặc viewer là admin; hoặc candidate xem chính mình.
    - public: ứng viên bật công khai (và tài khoản không bị khóa) mà chưa có đơn ứng tuyển như trên.
    - none: còn lại (tắt công khai và chưa nộp / đã rút hết; hoặc tài khoản bị khóa).
    - Candidate xem hồ sơ người khác: raise PermissionError.
    """
    v_role = getattr(viewer, "role", None) if not isinstance(viewer, dict) else viewer.get("role")
    v_id = getattr(viewer, "id", None) if not isinstance(viewer, dict) else viewer.get("id")

    if v_role == "admin":
        return "full"

    c_uid = getattr(candidate, "user_id", None) if not isinstance(candidate, dict) else candidate.get("user_id")
    c_active = getattr(candidate, "is_active", True) if not isinstance(candidate, dict) else candidate.get("is_active", True)
    c_public = getattr(candidate, "is_public", True) if not isinstance(candidate, dict) else candidate.get("is_public", True)

    if v_role == "candidate":
        if v_id is not None and c_uid is not None and v_id == c_uid:
            return "full"
        raise PermissionError("Ứng viên không có quyền xem hồ sơ của ứng viên khác.")

    if not c_active:
        return "none"

    # Kiểm tra đơn ứng tuyển chưa rút vào tin của employer
    has_active_app = False
    if applications:
        for app in applications:
            status = getattr(app, "status", None) if not isinstance(app, dict) else app.get("status")
            withdrawn_at = getattr(app, "withdrawn_at", None) if not isinstance(app, dict) else app.get("withdrawn_at")
            st_str = (status.value if hasattr(status, "value") else str(status or "")).upper()
            if st_str != "WITHDRAWN" and withdrawn_at is None:
                has_active_app = True
                break

    if has_active_app:
        return "full"

    if c_public:
        return "public"

    return "none"


class ProfileViewRateLimiter:
    """Bộ giới hạn tần suất xem hồ sơ theo employer (tối đa 60 lượt/phút)."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[int, deque[float]] = defaultdict(deque)

    def check_and_record(self, employer_id: int) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            q = self._requests[employer_id]
            while q and (now - q[0]) > self.window_seconds:
                q.popleft()
            if len(q) >= self.max_requests:
                oldest = q[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return False, retry_after
            q.append(now)
            return True, 0

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


profile_view_rate_limiter = ProfileViewRateLimiter()


def record_profile_view_if_needed(db, viewer_id: int, candidate_user_id: int, emp_apps: list, job_id: int | None):
    """Ghi nhật ký lượt xem hồ sơ có debounce 30 phút (lỗi không làm hỏng response)."""
    if viewer_id == candidate_user_id:
        return
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models.profile_view import ProfileView
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=30)
        existing = db.scalar(select(ProfileView).where(
            ProfileView.employer_user_id == viewer_id,
            ProfileView.candidate_user_id == candidate_user_id,
            ProfileView.viewed_at >= since,
        ))
        if not existing:
            first_app = next((a for a in emp_apps if (getattr(a.status, 'value', str(a.status)).upper() != 'WITHDRAWN' and a.withdrawn_at is None)), None)
            db.add(ProfileView(
                employer_user_id=viewer_id, candidate_user_id=candidate_user_id,
                application_id=first_app.id if first_app else None,
                context="with_job" if job_id else "profile_view",
            ))
            db.commit()
    except Exception:
        db.rollback()



def build_candidate_profile_payload(
    profile, cand_user, access: str, raw_skills: list,
    exps: list, edus: list, apps_to_you: list | None = None,
    match_data: dict | None = None,
) -> dict:
    """Whitelist serializer cho hồ sơ ứng viên (SEC-02: giấu contact khi public)."""
    payload = {
        "public_id": profile.public_id, "full_name": cand_user.full_name,
        "headline": profile.headline, "city": profile.location, "avatar": cand_user.avatar_url,
        "bio": profile.summary or profile.bio, "skills": raw_skills,
        "experiences": [
            {"id": e.id, "title": e.title, "company": e.company, "start_month": e.start_month, "end_month": e.end_month, "is_current": e.is_current, "description": e.description}
            for e in exps
        ],
        "educations": [
            {"id": ed.id, "school": ed.school, "major": ed.major, "degree": ed.degree, "start_year": ed.start_year, "end_year": ed.end_year}
            for ed in edus
        ],
        "social_links": {
            "github": safe_url(profile.github_url), "linkedin": safe_url(profile.linkedin_url), "portfolio": safe_url(profile.portfolio_url),
        },
        "access": access,
    }
    if access == "full":
        payload["phone"] = cand_user.phone
        payload["email"] = cand_user.email
        if apps_to_you is not None:
            payload["applications_to_you"] = apps_to_you
    if match_data:
        payload["match"] = match_data
    return payload

