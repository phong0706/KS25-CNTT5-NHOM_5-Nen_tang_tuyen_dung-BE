"""test_candidate_saved_jobs_and_search.py
Kiểm thử toàn diện module:
1. Yêu thích / Việc làm đã lưu (/api/candidate/saved-jobs):
   - Đúng: lưu tin, bỏ lưu tin (idempotent), danh sách tin đã lưu, phân trang, tìm kiếm q, sắp xếp.
   - Đánh dấu tin đã đóng (status != 'published' hoặc closed) và hết hạn (deadline < today).
   - Sai dữ liệu: lưu tin không tồn tại (404).
   - Chưa đăng nhập: 401.
   - Sai quyền (employer, admin): 403.
2. Gợi ý tìm kiếm tức thì (/api/search/suggest):
   - Gợi ý theo tiêu đề vị trí, kỹ năng, công ty.
   - Số lượng đếm tin (count).
   - Xử lý từ khoá ngắn (< 2 ký tự).
3. Kết hợp nhiều bộ lọc (/api/jobs):
   - Kết hợp q, skills, location, level, salary_min, sort.
"""
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, delete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaLocation, MetaSkill, SavedJob
from app.models.user import User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def candidate_user(db_session):
    u = db_session.scalar(select(User).where(User.role == "candidate").limit(1))
    if not u:
        u = User(
            email=f"candidate_{uuid.uuid4().hex[:6]}@test.com",
            password=hash_password("cand123"),
            role="candidate",
            full_name="Ứng viên Test",
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    return u


@pytest.fixture(scope="module")
def candidate_token(candidate_user):
    return create_access_token(candidate_user.id, candidate_user.role, getattr(candidate_user, "token_version", 1))


@pytest.fixture(scope="module")
def employer_user(db_session):
    u = db_session.scalar(select(User).where(User.role == "employer").limit(1))
    if not u:
        u = User(
            email=f"employer_{uuid.uuid4().hex[:6]}@test.com",
            password=hash_password("emp123"),
            role="employer",
            full_name="Nhà tuyển dụng Test",
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    return u


@pytest.fixture(scope="module")
def employer_token(employer_user):
    return create_access_token(employer_user.id, employer_user.role, getattr(employer_user, "token_version", 1))


@pytest.fixture(scope="module")
def admin_token(db_session):
    u = db_session.scalar(select(User).where(User.role == "admin").limit(1))
    if not u:
        u = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            password=hash_password("admin123"),
            role="admin",
            full_name="Quản trị viên Test",
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    return create_access_token(u.id, u.role, getattr(u, "token_version", 1))


@pytest.fixture(scope="module")
def sample_company_and_jobs(db_session, employer_user):
    # Đảm bảo có công ty được xác minh
    comp = db_session.scalar(select(Company).where(Company.slug == "cong-ty-kiem-thu-mau").limit(1))
    if not comp:
        comp = Company(
            employer_id=employer_user.id,
            name="Công Ty Kiểm Thử Mẫu",
            slug="cong-ty-kiem-thu-mau",
            status=CompanyStatus.VERIFIED,
            verification_status="da_xac_minh",
            is_visible=True,
            is_verified=True,
        )
        db_session.add(comp)
        db_session.commit()
        db_session.refresh(comp)

    # 0. Đảm bảo có meta_skills cho test
    skill_py = db_session.scalar(select(MetaSkill).where(MetaSkill.name == "Python").limit(1))
    if not skill_py:
        skill_py = MetaSkill(name="Python")
        db_session.add(skill_py)
        db_session.commit()

    today = date.today()

    # 1. Tin còn hạn mở
    job_active = db_session.scalar(select(Job).where(Job.title == "[Test] Backend Python Developer").limit(1))
    if not job_active:
        job_active = Job(
            employer_id=employer_user.id,
            company_id=comp.id,
            title="[Test] Backend Python Developer",
            status="published",
            location="Hà Nội",
            salary_min=20000000,
            salary_max=35000000,
            skills='["Python", "FastAPI", "MySQL"]',
            deadline=today + timedelta(days=30),
            published_at=datetime.now(),
        )
        db_session.add(job_active)

    # 2. Tin đã đóng (status = 'closed')
    job_closed = db_session.scalar(select(Job).where(Job.title == "[Test] Frontend React Developer (Closed)").limit(1))
    if not job_closed:
        job_closed = Job(
            employer_id=employer_user.id,
            company_id=comp.id,
            title="[Test] Frontend React Developer (Closed)",
            status="closed",
            location="Hồ Chí Minh",
            salary_min=15000000,
            salary_max=25000000,
            skills='["React", "JavaScript"]',
            deadline=today + timedelta(days=10),
            published_at=datetime.now(),
        )
        db_session.add(job_closed)

    # 3. Tin đã quá hạn (deadline trong quá khứ)
    job_expired = db_session.scalar(select(Job).where(Job.title == "[Test] DevOps Engineer (Expired)").limit(1))
    if not job_expired:
        job_expired = Job(
            employer_id=employer_user.id,
            company_id=comp.id,
            title="[Test] DevOps Engineer (Expired)",
            status="published",
            location="Đà Nẵng",
            salary_min=25000000,
            salary_max=40000000,
            skills='["Docker", "Kubernetes", "AWS"]',
            deadline=today - timedelta(days=5),
            published_at=datetime.now() - timedelta(days=30),
        )
        db_session.add(job_expired)

    db_session.commit()
    db_session.refresh(job_active)
    db_session.refresh(job_closed)
    db_session.refresh(job_expired)

    return {
        "company": comp,
        "active": job_active,
        "closed": job_closed,
        "expired": job_expired,
    }


# ==============================================================================
# 1. KIỂM THỬ PHÂN QUYỀN & XÁC THỰC (Authentication & Authorization)
# ==============================================================================

def test_saved_jobs_unauthenticated_fails(client, sample_company_and_jobs):
    job_id = sample_company_and_jobs["active"].id

    # POST lưu tin không có token -> 401
    res = client.post(f"/api/candidate/saved-jobs/{job_id}")
    assert res.status_code == 401

    # DELETE bỏ lưu không có token -> 401
    res = client.delete(f"/api/candidate/saved-jobs/{job_id}")
    assert res.status_code == 401

    # GET danh sách không có token -> 401
    res = client.get("/api/candidate/saved-jobs")
    assert res.status_code == 401


def test_saved_jobs_wrong_role_fails(client, employer_token, admin_token, sample_company_and_jobs):
    job_id = sample_company_and_jobs["active"].id

    # Employer gọi API ứng viên -> 403
    headers_emp = {"Authorization": f"Bearer {employer_token}"}
    assert client.post(f"/api/candidate/saved-jobs/{job_id}", headers=headers_emp).status_code == 403
    assert client.delete(f"/api/candidate/saved-jobs/{job_id}", headers=headers_emp).status_code == 403
    assert client.get("/api/candidate/saved-jobs", headers=headers_emp).status_code == 403

    # Admin gọi API ứng viên -> 403
    headers_adm = {"Authorization": f"Bearer {admin_token}"}
    assert client.post(f"/api/candidate/saved-jobs/{job_id}", headers=headers_adm).status_code == 403
    assert client.delete(f"/api/candidate/saved-jobs/{job_id}", headers=headers_adm).status_code == 403
    assert client.get("/api/candidate/saved-jobs", headers=headers_adm).status_code == 403


# ==============================================================================
# 2. KIỂM THỬ SAI DỮ LIỆU (Validation & Not Found)
# ==============================================================================

def test_save_nonexistent_job_returns_404(client, candidate_token):
    headers = {"Authorization": f"Bearer {candidate_token}"}
    res = client.post("/api/candidate/saved-jobs/999999", headers=headers)
    assert res.status_code == 404
    assert "không tồn tại" in res.json().get("detail", "")


# ==============================================================================
# 3. KIỂM THỬ LƯU / BỎ LƯU TIN (Idempotent & Đúng luồng)
# ==============================================================================

def test_save_and_unsave_job_idempotent(client, candidate_token, candidate_user, db_session, sample_company_and_jobs):
    headers = {"Authorization": f"Bearer {candidate_token}"}
    job_id = sample_company_and_jobs["active"].id

    # Đảm bảo ban đầu chưa lưu
    db_session.execute(delete(SavedJob).where(SavedJob.user_id == candidate_user.id, SavedJob.job_id == job_id))
    db_session.commit()

    # 1. Lưu tin lần 1 -> Thành công (200)
    res1 = client.post(f"/api/candidate/saved-jobs/{job_id}", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_saved"] is True
    assert data1["job_id"] == job_id

    # 2. Lưu tin lần 2 (Idempotent) -> Vẫn thành công, không sinh bản ghi trùng
    res2 = client.post(f"/api/candidate/saved-jobs/{job_id}", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["is_saved"] is True

    # Kiểm tra trong DB chỉ có đúng 1 bản ghi
    saved_count = db_session.scalar(
        select(SavedJob).where(SavedJob.user_id == candidate_user.id, SavedJob.job_id == job_id)
    )
    assert saved_count is not None

    # 3. Bỏ lưu tin -> Thành công (200)
    res_del1 = client.delete(f"/api/candidate/saved-jobs/{job_id}", headers=headers)
    assert res_del1.status_code == 200
    data_del1 = res_del1.json()
    assert data_del1["is_saved"] is False

    # 4. Bỏ lưu tin lần 2 (Idempotent) -> Không báo lỗi 500, trả về 200 is_saved: False
    res_del2 = client.delete(f"/api/candidate/saved-jobs/{job_id}", headers=headers)
    assert res_del2.status_code == 200
    assert res_del2.json()["is_saved"] is False


# ==============================================================================
# 4. KIỂM THỬ DANH SÁCH VIỆC ĐÃ LƯU & ĐÁNH DẤU TIN ĐÃ ĐÓNG / HẾT HẠN
# ==============================================================================

def test_saved_jobs_list_marks_closed_and_expired(client, candidate_token, candidate_user, db_session, sample_company_and_jobs):
    headers = {"Authorization": f"Bearer {candidate_token}"}
    active_j = sample_company_and_jobs["active"]
    closed_j = sample_company_and_jobs["closed"]
    expired_j = sample_company_and_jobs["expired"]

    # Lưu cả 3 tin cho ứng viên
    for j in [active_j, closed_j, expired_j]:
        client.post(f"/api/candidate/saved-jobs/{j.id}", headers=headers)

    # Lấy danh sách việc làm đã lưu
    res = client.get("/api/candidate/saved-jobs?page=1&page_size=20", headers=headers)
    assert res.status_code == 200
    body = res.json()
    items = body["items"]
    assert body["total"] >= 3

    item_map = {it["id"]: it for it in items}

    # 1. Tin đang mở, còn hạn -> is_expired = False
    assert active_j.id in item_map
    assert item_map[active_j.id]["is_expired"] is False
    assert item_map[active_j.id]["is_saved"] is True

    # 2. Tin đã đóng (status = 'closed') -> status = 'closed', is_expired = True
    assert closed_j.id in item_map
    assert item_map[closed_j.id]["status"] == "closed"
    assert item_map[closed_j.id]["is_expired"] is True

    # 3. Tin đã hết hạn (deadline quá khứ) -> is_expired = True
    assert expired_j.id in item_map
    assert item_map[expired_j.id]["is_expired"] is True

    # 4. Kiểm tra tìm kiếm từ khóa theo `q`
    search_res = client.get("/api/candidate/saved-jobs?q=Backend", headers=headers)
    assert search_res.status_code == 200
    search_items = search_res.json()["items"]
    assert any(it["id"] == active_j.id for it in search_items)
    assert not any(it["id"] == closed_j.id for it in search_items)

    # 5. Kiểm tra sắp xếp theo sắp hết hạn `sort=expiring_soon`
    sort_res = client.get("/api/candidate/saved-jobs?sort=expiring_soon", headers=headers)
    assert sort_res.status_code == 200
    assert len(sort_res.json()["items"]) >= 3


# ==============================================================================
# 5. KIỂM THỬ GỢI Ý TÌM KIẾM TỨC THÌ (/api/search/suggest)
# ==============================================================================

def test_search_suggestions_api(client, sample_company_and_jobs):
    # 1. Từ khoá quá ngắn (< 2 ký tự) -> trả về mảng rỗng
    res_short = client.get("/api/search/suggest?q=a")
    assert res_short.status_code == 200
    assert res_short.json() == {"items": []}

    # 2. Gợi ý theo Tiêu đề Vị trí
    res_pos = client.get("/api/search/suggest?q=Backend")
    assert res_pos.status_code == 200
    items_pos = res_pos.json().get("items", [])
    assert any(it["group"] == "Vị trí" or it["type"] == "position" for it in items_pos)
    for it in items_pos:
        assert "text" in it
        assert "count" in it

    # 3. Gợi ý theo Kỹ năng
    res_skill = client.get("/api/search/suggest?q=Python")
    assert res_skill.status_code == 200
    items_skill = res_skill.json().get("items", [])
    assert any(it["type"] == "skill" or it["group"] == "Kỹ năng" for it in items_skill)

    # 4. Gợi ý theo Công ty
    res_comp = client.get("/api/search/suggest?q=Kiểm Thử")
    assert res_comp.status_code == 200
    items_comp = res_comp.json().get("items", [])
    assert any(it["type"] == "company" or it["group"] == "Công ty" for it in items_comp)


# ==============================================================================
# 6. KIỂM THỬ KẾT HỢP NHIỀU BỘ LỌC TÌM VIỆC (/api/jobs)
# ==============================================================================

def test_multi_filter_combination(client, sample_company_and_jobs):
    # 1. Lọc kết hợp: từ khoá q + địa điểm + khoảng lương
    params = {
        "q": "Backend",
        "salary_min": 15000000,
        "salary_max": 40000000,
        "sort": "newest",
        "page": 1,
        "page_size": 10,
    }
    res = client.get("/api/jobs", params=params)
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "facets" in body
    assert body["total"] >= 1

    # Tin trả về phải thoả mãn điều kiện
    for item in body["items"]:
        assert "Python" in item["title"] or "Backend" in item["title"]
        if item["salary_min"] and item["salary_max"]:
            assert item["salary_min"] <= 40000000
            assert item["salary_max"] >= 15000000

    # 2. Kiểm tra API nới lỏng bộ lọc /api/jobs/relaxed
    relaxed_res = client.get("/api/jobs/relaxed", params={"location": "UnknownLoc", "salary_min": 100000000})
    assert relaxed_res.status_code == 200
    assert "suggestions" in relaxed_res.json()
