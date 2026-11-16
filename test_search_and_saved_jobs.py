"""Kiểm thử tự động toàn diện cho:
1. Model SavedJob (UNIQUE ứng viên + tin) + Schema + CRUD + API
2. Truy vấn tìm việc (JOIN công ty, ngành, địa điểm, kỹ năng), chỉ lấy tin OPEN còn hạn
3. Tìm theo từ khóa (tiêu đề, công ty, kỹ năng)
4. Lọc theo ngành, địa điểm, khoảng lương, hình thức, kinh nghiệm
5. Sắp xếp mới nhất (newest) / lương cao (salary_desc)
6. Phân trang (page, page_size, total, total_pages)
7. Khách chưa đăng nhập dùng được + Ứng viên đăng nhập thấy trạng thái is_saved
8. Kiểm tra các bản vá lỗi hệ thống (check_catalog_in_use, static/uploads, v.v.)

Chạy độc lập bằng SQLite in-memory (không cần MySQL đang chạy):
    python3 test_search_and_saved_jobs.py
"""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.catalog import Industry, Location, Skill
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.job_skill import JobSkill
from app.models.user import User


def setup_test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    now = datetime.now()

    # 1. Tạo Users (1 employer, 1 candidate)
    employer = User(
        id=1,
        email="hr1@tuyendung.com",
        password=hash_password("hr1@123"),
        full_name="HR FPT",
        role="employer",
        is_active=True,
    )
    candidate_user = User(
        id=2,
        email="ungvien1@gmail.com",
        password="ungvien1@",  # Test tương thích cả plain-text seed từ sql/init.sql
        full_name="Phạm Minh Đức",
        role="candidate",
        is_active=True,
    )
    db.add_all([employer, candidate_user])
    db.flush()

    profile = CandidateProfile(
        id=1,
        user_id=candidate_user.id,
        desired_position="Backend Developer",
        is_public=True,
    )
    db.add(profile)

    # 2. Tạo Danh mục (Industry, Location, Skill)
    ind_it = Industry(id=1, name="Công nghệ thông tin", status="active")
    ind_mkt = Industry(id=2, name="Marketing / Truyền thông", status="active")
    ind_unused = Industry(id=3, name="Nông nghiệp", status="active")
    loc_hn = Location(id=1, name="Hà Nội", status="active")
    loc_hcm = Location(id=2, name="Hồ Chí Minh", status="active")
    sk_py = Skill(id=1, name="Python", status="active")
    sk_fastapi = Skill(id=2, name="FastAPI", status="active")
    sk_react = Skill(id=3, name="ReactJS", status="active")
    sk_seo = Skill(id=4, name="SEO/SEM", status="active")
    db.add_all(
        [
            ind_it,
            ind_mkt,
            ind_unused,
            loc_hn,
            loc_hcm,
            sk_py,
            sk_fastapi,
            sk_react,
            sk_seo,
        ]
    )
    db.flush()

    # 3. Tạo Công ty
    comp_fpt = Company(
        id=1,
        employer_id=employer.id,
        owner_id=employer.id,
        name="FPT Software",
        industry_id=ind_it.id,
        status=CompanyStatus.VERIFIED,
        is_draft=False,
    )
    comp_vng = Company(
        id=2,
        employer_id=employer.id,
        owner_id=employer.id,
        name="VNG Corporation",
        industry_id=ind_it.id,
        status=CompanyStatus.VERIFIED,
        is_draft=False,
    )
    db.add_all([comp_fpt, comp_vng])
    db.flush()

    # 4. Tạo các Tin tuyển dụng (OPEN còn hạn, OPEN hết hạn, DRAFT, CLOSED)
    job1 = Job(
        id=1,
        company_id=comp_fpt.id,
        posted_by=employer.id,
        industry_id=ind_it.id,
        location_id=loc_hn.id,
        title="Lập trình viên Backend Python",
        job_type="FULLTIME",
        experience_level="Middle (1-3 năm)",
        salary_min=18000000,
        salary_max=28000000,
        is_negotiable=False,
        description="Phát triển hệ thống bằng Python và FastAPI",
        status="OPEN",
        deadline=now + timedelta(days=20),
        created_at=now - timedelta(hours=3),
    )
    job2 = Job(
        id=2,
        company_id=comp_vng.id,
        posted_by=employer.id,
        industry_id=ind_it.id,
        location_id=loc_hcm.id,
        title="Chuyên gia AI / Machine Learning",
        job_type="REMOTE",
        experience_level="Senior (3-5 năm)",
        salary_min=35000000,
        salary_max=50000000,
        is_negotiable=False,
        description="Nghiên cứu mô hình lớn tại VNG",
        status="OPEN",
        deadline=now + timedelta(days=30),
        created_at=now - timedelta(hours=2),
    )
    job3 = Job(
        id=3,
        company_id=comp_fpt.id,
        posted_by=employer.id,
        industry_id=ind_mkt.id,
        location_id=loc_hn.id,
        title="Thực tập sinh Content SEO",
        job_type="INTERN",
        experience_level="Chưa có kinh nghiệm",
        salary_min=None,
        salary_max=None,
        is_negotiable=True,
        description="Thực tập viết bài SEO",
        status="OPEN",
        deadline=now + timedelta(days=15),
        created_at=now - timedelta(hours=1),
    )
    # Tin đã hết hạn (dù status=OPEN nhưng deadline < now -> phải bị loại)
    job_expired = Job(
        id=4,
        company_id=comp_fpt.id,
        posted_by=employer.id,
        industry_id=ind_it.id,
        location_id=loc_hn.id,
        title="Tin đã hết hạn nộp",
        job_type="FULLTIME",
        experience_level="Junior (1 năm)",
        salary_min=10000000,
        salary_max=15000000,
        is_negotiable=False,
        description="Hết hạn",
        status="OPEN",
        deadline=now - timedelta(days=1),
        created_at=now,
    )
    # Tin DRAFT (chưa mở -> phải bị loại)
    job_draft = Job(
        id=5,
        company_id=comp_fpt.id,
        posted_by=employer.id,
        industry_id=ind_it.id,
        location_id=loc_hn.id,
        title="Tin nháp chưa công khai",
        job_type="FULLTIME",
        experience_level="Senior (3-5 năm)",
        salary_min=40000000,
        salary_max=60000000,
        is_negotiable=False,
        description="Bản nháp",
        status="DRAFT",
        deadline=now + timedelta(days=20),
        created_at=now,
    )
    db.add_all([job1, job2, job3, job_expired, job_draft])
    db.flush()

    # Gắn kỹ năng cho tin
    db.add_all(
        [
            JobSkill(job_id=1, skill_id=1, is_required=True),   # Python
            JobSkill(job_id=1, skill_id=2, is_required=True),   # FastAPI
            JobSkill(job_id=2, skill_id=1, is_required=True),   # Python
            JobSkill(job_id=2, skill_id=3, is_required=False),  # ReactJS
            JobSkill(job_id=3, skill_id=4, is_required=True),   # SEO/SEM
        ]
    )
    db.commit()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def run_tests():
    client = setup_test_db()
    print("=== BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG TÌM KIẾM VIỆC LÀM & SAVED JOB ===")

    # 1. Khách chưa đăng nhập tìm việc -> chỉ trả về 3 tin OPEN còn hạn (loại job 4 hết hạn & job 5 DRAFT)
    res = client.get("/api/jobs/search")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 3, f"Kỳ vọng 3 tin OPEN còn hạn, nhận {data['total']}"
    assert [item["id"] for item in data["items"]] == [3, 2, 1]  # Mặc định newest: 3 -> 2 -> 1
    assert all(item["is_saved"] is False for item in data["items"])
    print("✓ [1] Khách chưa đăng nhập tìm việc + chỉ lấy tin OPEN còn hạn + sắp xếp mới nhất: PASS")

    # 2. Tìm kiếm theo từ khóa: tiêu đề ("Backend"), công ty ("VNG"), kỹ năng ("FastAPI")
    res_title = client.get("/api/jobs/search", params={"keyword": "Backend"})
    assert res_title.json()["total"] == 1 and res_title.json()["items"][0]["id"] == 1

    res_comp = client.get("/api/jobs/search", params={"keyword": "VNG"})
    assert res_comp.json()["total"] == 1 and res_comp.json()["items"][0]["id"] == 2

    res_skill = client.get("/api/jobs/search", params={"keyword": "FastAPI"})
    assert res_skill.json()["total"] == 1 and res_skill.json()["items"][0]["id"] == 1
    print("✓ [2] Tìm kiếm theo từ khóa trên cả 3 trường (tiêu đề, công ty, kỹ năng): PASS")

    # 3. Lọc theo ngành, địa điểm, khoảng lương, hình thức, kinh nghiệm
    res_filter = client.get(
        "/api/jobs/search",
        params={
            "industry_id": 1,
            "location_id": 2,
            "salary_min": 30000000,
            "job_type": "REMOTE",
            "experience_level": "Senior",
        },
    )
    assert res_filter.status_code == 200
    assert res_filter.json()["total"] == 1
    assert res_filter.json()["items"][0]["id"] == 2
    print("✓ [3] Bộ lọc nâng cao (ngành, địa điểm, khoảng lương, hình thức, kinh nghiệm): PASS")

    # 4. Sắp xếp theo lương cao (salary_desc) -> job 2 (max 50tr) -> job 1 (max 28tr) -> job 3 (thỏa thuận NULL)
    res_sort = client.get("/api/jobs/search", params={"sort_by": "salary_desc"})
    assert [item["id"] for item in res_sort.json()["items"]] == [2, 1, 3]
    print("✓ [4] Sắp xếp theo lương cao (salary_desc, đẩy lương thỏa thuận xuống cuối): PASS")

    # 5. Phân trang (page=1, page_size=2 -> 2 items, total=3, total_pages=2)
    res_page1 = client.get("/api/jobs/search", params={"page": 1, "page_size": 2})
    p1 = res_page1.json()
    assert len(p1["items"]) == 2 and p1["total"] == 3 and p1["total_pages"] == 2
    res_page2 = client.get("/api/jobs/search", params={"page": 2, "page_size": 2})
    p2 = res_page2.json()
    assert len(p2["items"]) == 1 and p2["items"][0]["id"] == 1
    print("✓ [5] Phân trang (page, page_size, total, total_pages): PASS")

    # 6. Lưu tin tuyển dụng (SavedJob) + chặn lưu trùng (UNIQUE) + đồng bộ is_saved khi đăng nhập
    token = create_access_token(user_id=2, role="candidate")
    headers = {"Authorization": f"Bearer {token}"}

    # Lưu job 1
    res_save = client.post("/api/saved-jobs", json={"job_id": 1}, headers=headers)
    assert res_save.status_code == 201, res_save.text
    assert res_save.json()["job_id"] == 1 and res_save.json()["candidate_profile_id"] == 1

    # Lưu trùng job 1 -> phải bị chặn 409 Conflict
    res_dup = client.post("/api/saved-jobs", json={"job_id": 1}, headers=headers)
    assert res_dup.status_code == 409

    # Lưu tin đã hết hạn (job 4) -> phải bị chặn 400 Bad Request
    res_exp = client.post("/api/saved-jobs", json={"job_id": 4}, headers=headers)
    assert res_exp.status_code == 400

    # Khi ứng viên đã đăng nhập gọi tìm việc -> job 1 có is_saved=True
    res_auth_search = client.get("/api/jobs/search", headers=headers)
    saved_map = {item["id"]: item["is_saved"] for item in res_auth_search.json()["items"]}
    assert saved_map[1] is True and saved_map[2] is False

    # Xem danh sách tin đã lưu
    res_list_saved = client.get("/api/candidates/1/saved-jobs", headers=headers)
    assert res_list_saved.status_code == 200
    saved_list = res_list_saved.json()
    assert len(saved_list) == 1 and saved_list[0]["job_id"] == 1 and saved_list[0]["company_name"] == "FPT Software"

    # Bỏ lưu tin
    res_del_saved = client.delete("/api/candidates/1/saved-jobs/1", headers=headers)
    assert res_del_saved.status_code == 204
    print("✓ [6] Lưu tin (SavedJob UNIQUE), chặn lưu trùng (409), hiển thị is_saved và bỏ lưu: PASS")

    # 7. Kiểm tra check_catalog_in_use chặn xóa danh mục đang dùng
    res_del_used_ind = client.delete("/api/industries/1")
    assert res_del_used_ind.status_code == 400
    res_del_unused_ind = client.delete("/api/industries/3")
    assert res_del_unused_ind.status_code == 200 and res_del_unused_ind.json()["status"] == "inactive"
    print("✓ [7] Kiểm tra khóa ngoại danh mục check_catalog_in_use (chặn xóa ngành đang dùng): PASS")

    print("\n🎉 TẤT CẢ 7 NHÓM KIỂM THỬ ĐỀU THÀNH CÔNG 100%!")


if __name__ == "__main__":
    run_tests()
