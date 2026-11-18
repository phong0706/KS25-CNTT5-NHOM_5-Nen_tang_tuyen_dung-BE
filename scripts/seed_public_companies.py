"""Migration mở rộng bảng companies + Seed >= 12 công ty công khai (hư cấu cho phần bổ sung).
Cách chạy: cd backend && python scripts/seed_public_companies.py
"""
from datetime import date, timedelta
from pathlib import Path
import sys
from sqlalchemy import select, text

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.company import Company, CompanyStatus  # noqa: E402
from app.models.job import Job  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.public_company_rules import normalize_search_text  # noqa: E402

NEW_COMPANY_COLS = {
    "tagline": "VARCHAR(120) NULL AFTER name",
    "location_id": "INT NULL AFTER industry_id",
    "size_range": "ENUM('1-50','51-200','201-500','501-1000','1000+') NULL AFTER address",
    "founded_year": "SMALLINT NULL AFTER size_range",
    "is_visible": "BOOLEAN NOT NULL DEFAULT TRUE AFTER description",
    "is_verified": "BOOLEAN NOT NULL DEFAULT FALSE AFTER is_visible",
    "verified_at": "DATETIME NULL AFTER is_verified",
    "search_text": "VARCHAR(500) NULL AFTER verified_at",
}

FICTIONAL_SEED = [
    ("ngan-hang-so-dong-a", "Ngân hàng Số Đông Á", "Nền tảng ngân hàng số và thanh toán mở", 1, 2, "201-500", 2018, "https://dongadigital.example.vn", True, True, "Ngân hàng Số Đông Á phát triển hạ tầng thanh toán số, ví điện tử và dịch vụ ngân hàng mở cho doanh nghiệp vừa và nhỏ tại Việt Nam.", [
        ("Senior Backend Engineer (Java / Spring)", "Senior", "TP. Hồ Chí Minh", 32000000, 52000000, False, ["Java", "Spring Boot", "PostgreSQL", "Kafka"], 2),
        ("Cloud Security Engineer", "Middle", "TP. Hồ Chí Minh", 24000000, 38000000, False, ["AWS", "Docker", "Kubernetes"], 5),
        ("React Frontend Developer", "Junior", "TP. Hồ Chí Minh", 18000000, 28000000, False, ["React", "TypeScript", "JavaScript"], 7),
    ]),
    ("sao-khue-cloud-labs", "Sao Khuê Cloud Labs", "Giải pháp điện toán đám mây cho doanh nghiệp", 4, 3, "51-200", 2021, "https://saokhuecloud.example.vn", True, True, "Sao Khuê Cloud Labs cung cấp dịch vụ tự động hóa hạ tầng Kubernetes, giám sát hệ thống và chuyển đổi số tại Đà Nẵng.", [
        ("Site Reliability Engineer (SRE)", "Middle", "Đà Nẵng", 25000000, 40000000, False, ["Kubernetes", "Terraform", "AWS", "Python"], 1),
        ("DevOps Engineer", "Junior", "Đà Nẵng", 17000000, 26000000, False, ["Docker", "CI/CD", "Linux"], 4),
    ]),
    ("trung-tam-ai-sao-phuong-nam", "Trung tâm Nghiên cứu và Phát triển Hạ tầng Trí tuệ Nhân tạo Sao Phương Nam", "Nghiên cứu mô hình ngôn ngữ tiếng Việt và thị giác máy tính", 3, 1, "501-1000", 2020, "https://saophuongnam.example.vn", True, True, "Đơn vị tập trung phát triển hạ tầng huấn luyện AI quy mô lớn, xử lý ngôn ngữ tự nhiên tiếng Việt và hệ thống gợi ý thông minh.", [
        ("Senior Machine Learning Engineer", "Senior", "Hà Nội", 40000000, 65000000, False, ["Python", "PyTorch", "Docker", "Kubernetes"], 3),
        ("Data Platform Engineer", "Middle", "Hà Nội", 26000000, 42000000, False, ["Python", "SQL", "Apache Spark"], 6),
    ]),
    ("phan-mem-nhung-hai-dang", "Phần mềm Nhúng Hải Đăng", "Thiết kế firmware cho thiết bị công nghiệp IoT", 1, 4, "1-50", 2019, "https://haidangiot.example.vn", True, False, "Chuyên phát triển phần mềm nhúng C/C++ và cổng thu thập dữ liệu IoT cho nhà máy thông minh.", []),
    ("cong-ty-noi-bo-an", "Doanh nghiệp Công nghệ Nội bộ Ẩn", "Hồ sơ đang tạm ẩn", 1, 1, "1-50", 2022, None, False, False, "Hồ sơ nội bộ không hiển thị công khai.", [
        ("Internal QA Engineer", "Junior", "Hà Nội", 15000000, 20000000, False, ["Selenium", "SQL"], 2),
    ]),
    ("an-ninh-mang-lam-son", "An ninh mạng Lam Sơn", "Kiểm thử xâm nhập và giám sát an toàn thông tin 24/7", 4, 1, "51-200", 2017, "https://lamsonsec.example.vn", True, True, "Đội ngũ chuyên gia an toàn thông tin thực hiện đánh giá bảo mật ứng dụng web, di động và hạ tầng đám mây.", [
        ("Security Analyst (SOC L2)", "Middle", "Hà Nội", None, None, True, ["Linux", "SIEM", "Python"], 2),
        ("Penetration Tester", "Senior", "Hà Nội", None, None, True, ["OWASP", "Security", "Python"], 8),
    ]),
    ("du-lieu-lon-cuu-long", "Dữ liệu lớn Cửu Long", None, 3, 5, "1-50", None, None, True, False, None, [
        ("Data Analyst", "Junior", "Cần Thơ", 14000000, 22000000, False, ["SQL", "Python", "Power BI"], 3),
        ("Backend Python Developer", "Middle", "Cần Thơ", 20000000, 32000000, False, ["Python", "FastAPI", "MySQL"], 9),
    ]),
    ("tu-dong-hoa-kiem-thu-anh-duong", "Tự động hóa Kiểm thử Ánh Dương", "Dịch vụ kiểm thử tự động hóa cho sản phẩm SaaS", 6, 6, "51-200", 2020, "https://anhduongqa.example.vn", True, False, "Cung cấp giải pháp kiểm thử hiệu năng và kiểm thử tự động đa trình duyệt cho các đội ngũ sản phẩm.", [
        ("Automation QA Engineer", "Middle", "Bình Dương", 19000000, 29000000, False, ["Playwright", "TypeScript", "API Testing"], 4),
        ("Manual QA Engineer", "Junior", "Bình Dương", None, None, True, ["SQL", "Postman"], 10),
    ]),
]


def ensure_schema_and_indexes() -> None:
    with engine.begin() as conn:
        existing = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM companies")).fetchall()}
        for col, ddl in NEW_COMPANY_COLS.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE companies ADD COLUMN `{col}` {ddl}"))
        idx_c = {r[2] for r in conn.execute(text("SHOW INDEX FROM companies")).fetchall()}
        for name, cols in [("idx_companies_visible_name", "(is_visible, name)"), ("idx_companies_industry_id", "(industry_id)"), ("idx_companies_location_id", "(location_id)"), ("idx_companies_search_text", "(search_text)")]:
            if name not in idx_c:
                conn.execute(text(f"ALTER TABLE companies ADD INDEX `{name}` {cols}"))
        idx_j = {r[2] for r in conn.execute(text("SHOW INDEX FROM jobs")).fetchall()}
        if "idx_jobs_company_status_pub" not in idx_j:
            conn.execute(text("ALTER TABLE jobs ADD INDEX `idx_jobs_company_status_pub` (company_id, status, published_at)"))


def run_seed() -> None:
    ensure_schema_and_indexes()
    db = SessionLocal()
    try:
        for c in db.scalars(select(Company)).all():
            if not c.location_id and c.address:
                c.location_id = 2 if ("Hồ Chí Minh" in c.address or "Quận" in c.address) else (3 if "Đà Nẵng" in c.address else 1)
            c.search_text = normalize_search_text(c.name, c.tagline, c.address)[:500]
            if c.id in (7, 8, 9, 10, 11, 12):
                c.is_visible, c.is_draft, c.is_verified = True, False, True
                c.size_range = None
                c.founded_year = None
                c.logo_url = None
                c.cover_url = None
                if not c.description:
                    c.description = f"{c.name} là doanh nghiệp hoạt động trong lĩnh vực công nghệ và dịch vụ số tại Việt Nam."

        emp = db.scalar(select(User).where(User.role == "employer").order_by(User.id.asc()))
        if not emp:
            emp = User(email="demo.employer@techrecruit.local", password=hash_password("DemoPass123!"), full_name="Demo Employer", role="employer", is_active=True)
            db.add(emp); db.flush()

        for slug, name, tag, ind_id, loc_id, sz, yr, web, vis, ver, desc, jobs_spec in FICTIONAL_SEED:
            comp = db.scalar(select(Company).where(Company.slug == slug))
            if not comp:
                comp = Company(employer_id=emp.id, owner_id=emp.id, slug=slug, name=name, status=CompanyStatus.VERIFIED if ver else CompanyStatus.PENDING, is_draft=False)
                db.add(comp); db.flush()
            comp.name, comp.tagline, comp.industry_id, comp.location_id = name, tag, ind_id, loc_id
            comp.size_range, comp.founded_year, comp.website = sz, yr, web
            comp.is_visible, comp.is_verified, comp.description, comp.is_draft = vis, ver, desc, False
            comp.search_text = normalize_search_text(name, tag, None)[:500]
            db.flush()

            existing_cnt = db.execute(text("SELECT COUNT(*) FROM jobs WHERE company_id = :cid"), {"cid": comp.id}).scalar() or 0
            if existing_cnt == 0:
                for title, lvl, loc_name, smin, smax, is_neg, sks, days_ago in jobs_spec:
                    j = Job(
                        employer_id=comp.employer_id, company_id=comp.id, title=title, level=lvl,
                        work_type="Toàn thời gian", location=loc_name, quantity=2,
                        deadline=date.today() + timedelta(days=30),
                        description=f"Tuyển dụng vị trí {title} tại {name}.", requirements="Tối thiểu 1 năm kinh nghiệm thực tế.",
                        skills=sks, salary_min=smin, salary_max=smax, is_salary_negotiable=is_neg, status="published",
                    )
                    db.add(j); db.flush()
                    db.execute(text("UPDATE jobs SET published_at = NOW() - INTERVAL :d DAY, created_at = NOW() - INTERVAL :d DAY WHERE id = :jid"), {"d": days_ago, "jid": j.id})
        db.commit()
        print("[SEED] Hoàn tất mở rộng bảng companies và seed dữ liệu công ty công khai.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
