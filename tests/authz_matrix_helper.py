"""Helper cho test ma trận phân quyền (tách khỏi test để mỗi file <= 200 dòng)."""
import inspect
from pathlib import Path
import re
from fastapi.routing import APIRoute

# Whitelist tường minh các route công khai có chủ đích (mỗi dòng kèm lý do)
PUBLIC_WHITELIST: dict[tuple[str, str], str] = {
    ("GET", "/"): "Root health/info endpoint công khai",
    ("GET", "/health"): "Health check hệ thống",
    ("GET", "/api/health"): "Health check API",
    ("POST", "/api/auth/login"): "Đăng nhập tài khoản",
    ("POST", "/api/auth/register"): "Đăng ký tài khoản mới",
    ("POST", "/api/auth/forgot-password"): "Yêu cầu mã khôi phục mật khẩu",
    ("POST", "/api/auth/reset-password"): "Đặt lại mật khẩu bằng mã OTP",
    ("GET", "/api/jobs"): "Tìm kiếm việc làm công khai",
    ("GET", "/api/jobs/open"): "Danh sách việc làm đang mở công khai",
    ("GET", "/api/jobs/search"): "Tìm kiếm việc làm công khai (legacy)",
    ("GET", "/api/jobs/relaxed"): "Gợi ý việc làm mở rộng khi ít kết quả",
    ("GET", "/api/jobs/{job_id}"): "Xem chi tiết tin tuyển dụng công khai",
    ("GET", "/api/v1/open-jobs"): "Danh sách việc làm mở công khai (v1)",
    ("GET", "/api/v1/jobs/{job_id}"): "Chi tiết việc làm công khai (v1)",
    ("GET", "/api/companies"): "Danh sách công ty công khai",
    ("GET", "/api/companies/featured"): "Danh sách công ty nổi bật trang chủ",
    ("GET", "/api/companies/{slug}"): "Chi tiết công ty công khai",
    ("GET", "/api/companies/{slug}/jobs"): "Danh sách tin của công ty công khai",
    ("GET", "/api/home/companies"): "Công ty hiển thị trên trang chủ",
    ("GET", "/api/home/featured-companies"): "Công ty nổi bật trang chủ",
    ("GET", "/api/home/salary-by-skill"): "Thống kê lương theo kỹ năng trang chủ",
    ("GET", "/api/home/salary-insights"): "Thống kê lương trang chủ",
    ("GET", "/api/stats/home"): "Số liệu thống kê trang chủ",
    ("GET", "/api/meta/nav"): "Metadata mega menu điều hướng công khai",
    ("GET", "/api/meta/locations"): "Danh mục địa điểm công khai",
    ("GET", "/api/meta/levels"): "Danh mục cấp bậc công khai",
    ("GET", "/api/meta/work-types"): "Danh mục hình thức làm việc công khai",
    ("GET", "/api/meta/categories"): "Danh mục ngành nghề/chuyên môn công khai",
    ("GET", "/api/meta/skills"): "Danh mục kỹ năng công khai",
    ("GET", "/api/meta/cv-templates"): "Danh mục mẫu CV công khai",
    ("GET", "/api/meta/review-statuses"): "Danh mục trạng thái đánh giá công khai",
    ("GET", "/api/meta/quick-filters"): "Danh mục bộ lọc nhanh công khai",
    ("GET", "/api/meta/application-statuses"): "Danh mục trạng thái hồ sơ công khai",
    ("GET", "/api/meta/withdraw-reasons"): "Danh mục lý do rút hồ sơ công khai",
    ("GET", "/api/meta/rejection-reasons"): "Danh mục lý do từ chối ứng viên",
    ("GET", "/api/meta/salary-ranges"): "Danh mục khoảng lương",
    ("GET", "/api/industries"): "Danh mục ngành nghề công khai (chỉ đọc)",
    ("GET", "/api/industries/{industry_id}"): "Chi tiết ngành nghề công khai",
    ("GET", "/api/locations"): "Danh mục địa điểm công khai (chỉ đọc)",
    ("GET", "/api/locations/{location_id}"): "Chi tiết địa điểm công khai",
    ("GET", "/api/skills"): "Danh mục kỹ năng công khai (chỉ đọc)",
    ("GET", "/api/skills/{skill_id}"): "Chi tiết kỹ năng công khai",
    ("GET", "/api/search/suggest"): "Gợi ý từ khóa tìm kiếm công khai",
    ("GET", "/api/salary-lookup"): "Tra cứu mức lương công khai",
    ("GET", "/api/salary/insights"): "Phân tích mức lương công khai",
    ("GET", "/api/salary/skills-benchmark"): "So sánh lương theo kỹ năng công khai",
    ("GET", "/api/tools/rules/{tool}"): "Quy tắc công cụ tính lương/thuế/BHTN công khai",
    ("POST", "/api/tools/calculate/tax"): "Tính thuế TNCN công khai",
    ("GET", "/api/interview-questions"): "Đọc danh sách câu hỏi phỏng vấn công khai (chế độ đọc)",
    ("GET", "/api/interview-questions/random"): "Lấy câu hỏi phỏng vấn ngẫu nhiên công khai",
    ("GET", "/api/interview-questions/{question_id}"): "Chi tiết câu hỏi phỏng vấn công khai",
    ("GET", "/api/personality-test/questions"): "Bộ câu hỏi trắc nghiệm tính cách công khai",
    ("POST", "/api/personality-test/submit"): "Chấm điểm trắc nghiệm tính cách công khai",
    ("GET", "/api/candidate/cover-letter-templates"): "Mẫu thư giới thiệu tham khảo công khai",
    ("GET", "/api/profiles/{profile_id}"): "Xem hồ sơ công khai (ẩn nếu is_public=False)",
    ("GET", "/api/career-path"): "Lộ trình nghề nghiệp công khai",
    ("POST", "/api/career-path"): "Tính gợi ý lộ trình nghề nghiệp công khai",
    ("GET", "/career-path"): "Lộ trình nghề nghiệp công khai (alias)",
    ("POST", "/career-path"): "Tính gợi ý lộ trình nghề nghiệp công khai (alias)",
    ("GET", "/uploads/logos/{filename}"): "Tệp ảnh logo công ty công khai",
}


def extract_route_roles(route: APIRoute) -> set[str] | None:
    """Đọc tập vai trò được phép từ dependency tree của route. Trả None nếu là route công khai."""
    roles: set[str] = set()
    stack = list(getattr(route.dependant, "dependencies", []) or [])
    while stack:
        dep = stack.pop()
        call = getattr(dep, "call", None)
        if call is not None:
            if hasattr(call, "_required_roles"):
                roles.update(call._required_roles)
            else:
                qname = getattr(call, "__qualname__", "")
                if "require_candidate" in qname:
                    roles.add("candidate")
                elif "get_employer_scope" in qname or "_require_employer" in qname:
                    roles.update({"employer", "recruiter"})
                elif "_require_admin_or_operator" in qname:
                    roles.update({"admin", "operator"})
                elif "_require_admin" in qname:
                    roles.add("admin")
                else:
                    try:
                        nl = inspect.getclosurevars(call).nonlocals
                        if isinstance(nl.get("roles"), (tuple, list, set)):
                            roles.update(nl["roles"])
                    except Exception:
                        pass
        stack.extend(getattr(dep, "dependencies", []) or [])
    return roles if roles else None


def materialize_path(path: str) -> str:
    """Thay path params bằng giá trị giả lập an toàn để gọi thử HTTP."""
    def _rep(match: re.Match) -> str:
        name = match.group(1)
        if "slug" in name:
            return "nonexistent-slug-999999"
        if "public_id" in name:
            return "nonexistent_public_id_9999"
        if "filename" in name:
            return "nonexistent_logo_9999.webp"
        if "tool" in name:
            return "gross-net"
        if "code" in name:
            return "invalid_code"
        return "999999"

    return re.sub(r"\{([^}]+)\}", _rep, path)


def write_authz_matrix_doc(rows: list[tuple[str, str, bool, str, str]], out_path: Path) -> None:
    """Ghi bảng ma trận phân quyền tự động ra docs/authz-matrix.md."""
    lines = [
        "# Ma trận Phân quyền API (Tự sinh từ `tests/test_authz_matrix.py`)",
        "",
        f"Tổng số route kiểm tra: **{len(rows)}**.",
        "",
        "| Method | Route | Công khai? | Vai trò được phép | Kết quả test (5 danh tính) |",
        "|---|---|---|---|---|",
    ]
    for method, path, is_pub, roles_str, result_str in rows:
        lines.append(f"| `{method}` | `{path}` | {'Có' if is_pub else 'Không'} | {roles_str} | {result_str} |")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_raw_test_tables(db) -> None:
    """Tạo các bảng raw-SQL chưa có trong ORM Base trên DB test (idempotent)."""
    from sqlalchemy import text

    ddls = [
        """CREATE TABLE IF NOT EXISTS interview_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category_id INT NOT NULL DEFAULT 1,
            level_id INT NOT NULL DEFAULT 1,
            question TEXT NOT NULL,
            answer_hint TEXT NULL,
            is_published TINYINT(1) NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS interview_practice (
            id INT AUTO_INCREMENT PRIMARY KEY,
            candidate_id INT NOT NULL,
            question_id INT NOT NULL,
            practiced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_cand_q (candidate_id, question_id)
        )""",
        """CREATE TABLE IF NOT EXISTS candidate_cover_letters (
            id INT AUTO_INCREMENT PRIMARY KEY,
            candidate_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS personality_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            question_text TEXT NOT NULL,
            trait VARCHAR(50) NULL,
            order_index INT NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS cv_templates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            slug VARCHAR(80) NOT NULL,
            name VARCHAR(120) NOT NULL,
            category VARCHAR(80) NULL,
            tagline VARCHAR(255) NULL,
            ats_friendly TINYINT(1) NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS calc_rules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tool_slug VARCHAR(80) NOT NULL,
            effective_from DATE NULL,
            source VARCHAR(255) NULL,
            rules_json TEXT NOT NULL
        )""",
    ]
    for ddl in ddls:
        db.execute(text(ddl))
    from sqlalchemy import inspect
    if "source" not in {c["name"] for c in inspect(db.bind).get_columns("calc_rules")}:
        db.execute(text("ALTER TABLE calc_rules ADD COLUMN source VARCHAR(255) NULL"))
    db.commit()
