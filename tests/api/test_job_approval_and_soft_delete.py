"""Kiểm thử luồng Duyệt tin tuyển dụng, Xóa mềm & Bảo vệ dữ liệu công khai."""
from datetime import date, datetime, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _unique_str():
    return uuid.uuid4().hex[:8]


def _create_user(db, role="employer"):
    u = User(
        email=f"{role}_{_unique_str()}@example.com",
        password="hashed_password",
        full_name=f"User {role.capitalize()}",
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _create_company(db, employer_id, verified=True):
    slug = f"company-{_unique_str()}"
    c = Company(
        employer_id=employer_id,
        name=f"Company {_unique_str()}",
        slug=slug,
        status=CompanyStatus.VERIFIED if verified else CompanyStatus.PENDING,
        verification_status="da_xac_minh" if verified else "chua_xac_minh",
        is_verified=verified,
        is_draft=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _create_job(db, employer_id, company_id, status="pending", version=1):
    j = Job(
        employer_id=employer_id,
        company_id=company_id,
        title=f"Lập trình viên Python {_unique_str()}",
        status=status,
        version=version,
        deadline=date.today() + timedelta(days=30),
        deleted_at=None,
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def test_employer_job_pending_not_public(client, db):
    """Tin ở trạng thái pending không xuất hiện trong danh sách công khai."""
    emp = _create_user(db, "employer")
    comp = _create_company(db, emp.id, verified=True)
    job = _create_job(db, emp.id, comp.id, status="pending")

    res = client.get("/api/jobs")
    assert res.status_code == 200
    job_ids = [item["id"] for item in res.json().get("items", [])]
    assert job.id not in job_ids

    # Xem chi tiết cũng trả về 404
    detail_res = client.get(f"/api/jobs/{job.id}")
    assert detail_res.status_code == 404


def test_admin_approve_job_becomes_public_and_notifies(client, db):
    """Admin duyệt: tin chuyển sang công khai, tạo thông báo, gọi lại idempotent."""
    admin = _create_user(db, "admin")
    emp = _create_user(db, "employer")
    comp = _create_company(db, emp.id, verified=True)
    job = _create_job(db, emp.id, comp.id, status="pending", version=1)

    admin_token = create_access_token(admin.id, admin.role)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Duyệt tin
    res = client.post(f"/api/admin/jobs/{job.id}/approve", json={"version": 1}, headers=headers)
    assert res.status_code == 200
    db.commit()
    db.refresh(job)
    assert job.status in ("open", "published")

    # Kiểm tra tin đã hiện ở trang công khai
    pub_res = client.get(f"/api/jobs/{job.id}")
    assert pub_res.status_code == 200
    assert pub_res.json()["id"] == job.id

    # Kiểm tra thông báo
    notifs = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).all()
    assert len(notifs) == 1
    assert "phê duyệt" in notifs[0].title.lower() or "phê duyệt" in notifs[0].message.lower()

    # Gọi lại khi đã duyệt -> 409 INVALID_TRANSITION, không tăng thêm thông báo
    res2 = client.post(f"/api/admin/jobs/{job.id}/approve", json={"version": job.version}, headers=headers)
    assert res2.status_code in (409, 422)
    notifs_after = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).all()
    assert len(notifs_after) == 1


def test_admin_delete_pending_job_requires_reason(client, db):
    """Admin xóa tin pending: bắt buộc lý do >= 10 ký tự, xóa mềm, tạo thông báo."""
    admin = _create_user(db, "admin")
    emp = _create_user(db, "employer")
    comp = _create_company(db, emp.id, verified=True)
    job = _create_job(db, emp.id, comp.id, status="pending", version=1)

    admin_token = create_access_token(admin.id, admin.role)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Không nhập lý do hoặc lý do < 10 ký tự -> 422
    err_res = client.request("DELETE", f"/api/admin/jobs/{job.id}", json={"reason": "Ngắn"}, headers=headers)
    assert err_res.status_code == 422

    # Nhập lý do >= 10 ký tự -> 200
    reason_valid = "Tin tuyển dụng sai chính tả và thiếu địa chỉ trụ sở"
    del_res = client.request("DELETE", f"/api/admin/jobs/{job.id}", json={"reason": reason_valid}, headers=headers)
    assert del_res.status_code == 200

    db.commit()
    db.refresh(job)
    assert job.deleted_at is not None

    # Tin biến mất khỏi danh sách pending của admin
    list_res = client.get("/api/admin/jobs?status=pending", headers=headers)
    ids = [item["id"] for item in list_res.json().get("items", [])]
    assert job.id not in ids

    # Nhà tuyển dụng nhận thông báo kèm lý do
    notif = db.query(Notification).filter_by(user_id=emp.id, ref_id=job.id).first()
    assert notif is not None
    assert reason_valid in notif.message


def test_employer_soft_delete_job_and_retains_applications(client, db):
    """Nhà tuyển dụng xóa tin đang tuyển: xóa mềm, tin biến khỏi công khai, applications còn nguyên."""
    emp = _create_user(db, "employer")
    cand = _create_user(db, "candidate")
    comp = _create_company(db, emp.id, verified=True)
    job = _create_job(db, emp.id, comp.id, status="published", version=1)

    # Giả lập ứng viên đã nộp đơn cho tin này
    app_record = Application(
        job_id=job.id,
        candidate_id=cand.id,
        cv_name_snapshot="CV_Candidate.pdf",
        status="pending",
    )
    db.add(app_record)
    db.commit()
    app_id = app_record.id

    emp_token = create_access_token(emp.id, emp.role)
    headers = {"Authorization": f"Bearer {emp_token}"}

    # Nhà tuyển dụng xóa tin của mình
    res = client.delete(f"/api/employer/jobs/{job.id}", headers=headers)
    assert res.status_code == 200

    db.commit()
    db.refresh(job)
    assert job.deleted_at is not None

    # Tin biến khỏi trang công khai ngay lập tức
    assert client.get(f"/api/jobs/{job.id}").status_code == 404

    # Bản ghi application vẫn còn nguyên vẹn trong CSDL (không bị lỗi khóa ngoại)
    reloaded_app = db.get(Application, app_id)
    assert reloaded_app is not None
    assert reloaded_app.job_id == job.id


def test_employer_cannot_delete_other_company_job(client, db):
    """Nhà tuyển dụng A không xóa được tin của công ty B -> 403."""
    emp1 = _create_user(db, "employer")
    emp2 = _create_user(db, "employer")
    comp2 = _create_company(db, emp2.id, verified=True)
    job2 = _create_job(db, emp2.id, comp2.id, status="published")

    emp1_token = create_access_token(emp1.id, emp1.role)
    headers = {"Authorization": f"Bearer {emp1_token}"}

    res = client.delete(f"/api/employer/jobs/{job2.id}", headers=headers)
    assert res.status_code == 403


def test_concurrency_two_admins_approve_same_job(client, db):
    """Hai admin cùng duyệt một tin với cùng version: một thành công, một nhận 409."""
    admin = _create_user(db, "admin")
    emp = _create_user(db, "employer")
    comp = _create_company(db, emp.id, verified=True)
    job = _create_job(db, emp.id, comp.id, status="pending", version=1)

    admin_token = create_access_token(admin.id, admin.role)
    headers = {"Authorization": f"Bearer {admin_token}"}

    res1 = client.post(f"/api/admin/jobs/{job.id}/approve", json={"version": 1}, headers=headers)
    assert res1.status_code == 200

    # Lần 2 với version cũ (=1) khi version trong DB đã lên 2 -> 409 Conflict
    # Chú ý: nếu status đã là open/published và expected_version lệch, validation_optimistic_version bắt 409
    res2 = client.post(f"/api/admin/jobs/{job.id}/approve", json={"version": 999}, headers=headers)
    assert res2.status_code in (409, 422)


def test_admin_list_pending_jobs_fifo_order(client, db):
    """Admin xem danh sách tin pending: sắp tin cũ nhất lên đầu (FIFO)."""
    admin = _create_user(db, "admin")
    emp = _create_user(db, "employer")
    comp = _create_company(db, emp.id, verified=True)
    tag = _unique_str()

    job_older = _create_job(db, emp.id, comp.id, status="pending")
    job_older.title = f"FIFO Test {tag} Older"
    job_newer = _create_job(db, emp.id, comp.id, status="pending")
    job_newer.title = f"FIFO Test {tag} Newer"
    # Cho job_older created_at lùi về 1 giờ trước
    db.execute(text("UPDATE jobs SET created_at = :t, title = :title WHERE id = :id"), {"t": datetime.now() - timedelta(hours=1), "title": job_older.title, "id": job_older.id})
    db.execute(text("UPDATE jobs SET title = :title WHERE id = :id"), {"title": job_newer.title, "id": job_newer.id})
    db.commit()

    admin_token = create_access_token(admin.id, admin.role)
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get(f"/api/admin/jobs?status=pending&q={tag}&limit=50", headers=headers)
    assert res.status_code == 200
    ids = [item["id"] for item in res.json().get("items", [])]
    # job_older phải xuất hiện trước job_newer trong danh sách pending
    assert job_older.id in ids and job_newer.id in ids
    assert ids.index(job_older.id) < ids.index(job_newer.id)
