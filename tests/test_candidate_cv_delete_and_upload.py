"""Integration tests: Nghiệp vụ xóa mềm CV, hạn mức, bảo mật và upload.
Tuân thủ techrecruit-rules: < 200 dòng, dọn dẹp sau test, chạy trên app_db_test.
"""
import os
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, CV, ApplicationStatus
from app.models.audit_log import AuditLog
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.services.cv_service import CV_STORAGE_DIR

client = TestClient(app)

@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def _user(db, role, name):
    u = User(email=f"{name}_{uuid.uuid4().hex[:6]}@test.vn", password=hash_password("pw123"), role=role, full_name=f"U_{name}", is_active=True, token_version=1)
    db.add(u); db.commit(); db.refresh(u)
    return u, create_access_token(u.id, u.role, 1)

def _create_cv_file(stored_name, content=None):
    os.makedirs(CV_STORAGE_DIR, exist_ok=True)
    p = os.path.join(CV_STORAGE_DIR, stored_name)
    with open(p, "wb") as f:
        f.write(content or (b"%PDF-1.4\n" + b"X" * 1500 + b"\n%%EOF"))
    return p

def test_delete_unused_cv_soft_deletes_and_removes_file(db):
    cand, token = _user(db, "candidate", "cand1")
    stored = f"test_cv_{uuid.uuid4().hex}.pdf"
    fp = _create_cv_file(stored)
    cv = CV(candidate_id=cand.id, original_name="unused.pdf", stored_name=stored, mime_type="application/pdf", size_bytes=1520, is_default=False)
    db.add(cv); db.commit(); db.refresh(cv)

    res = client.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204

    # DB: dòng vẫn còn nhưng có deleted_at
    db.commit(); db.refresh(cv)
    assert cv.deleted_at is not None
    # File vật lý đã bị xóa vì không có đơn nào dùng
    assert not os.path.isfile(fp)

    # Nhật ký AuditLog được ghi
    log = db.scalar(select(AuditLog).where(AuditLog.target_id == cv.id, AuditLog.action == "DELETE_CV"))
    assert log is not None
    assert log.actor_id == cand.id

def test_delete_used_cv_soft_deletes_and_keeps_file_for_employer(db):
    cand, token = _user(db, "candidate", "cand2")
    emp, emp_token = _user(db, "employer", "emp1")
    comp = Company(name="Co1", slug=f"co1-{uuid.uuid4().hex[:6]}", employer_id=emp.id)
    db.add(comp); db.commit(); db.refresh(comp)
    job = Job(title="Job 1", company_id=comp.id, employer_id=emp.id, status="published")
    db.add(job); db.commit(); db.refresh(job)

    stored = f"test_cv_{uuid.uuid4().hex}.pdf"
    fp = _create_cv_file(stored)
    cv = CV(candidate_id=cand.id, original_name="used.pdf", stored_name=stored, mime_type="application/pdf", size_bytes=1520, is_default=True)
    db.add(cv); db.commit(); db.refresh(cv)

    app_obj = Application(candidate_id=cand.id, job_id=job.id, cv_id=cv.id, status=ApplicationStatus.SUBMITTED.value)
    db.add(app_obj); db.commit(); db.refresh(app_obj)

    res = client.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204

    db.commit(); db.refresh(cv)
    assert cv.deleted_at is not None
    # File vật lý PHẢI CÒN để nhà tuyển dụng xem
    assert os.path.isfile(fp)

    # Danh sách của ứng viên không còn CV này
    list_res = client.get("/api/candidate/cvs", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    assert not any(c["id"] == cv.id for c in list_res.json())

    # Employer vẫn tải/xem được CV này qua endpoint đơn ứng tuyển
    emp_file_res = client.get(f"/api/candidate/cvs/{cv.id}/file", headers={"Authorization": f"Bearer {emp_token}"})
    assert emp_file_res.status_code == 200

def test_delete_default_cv_reassigns_newest_remaining(db):
    cand, token = _user(db, "candidate", "cand3")
    cv1 = CV(candidate_id=cand.id, original_name="c1.pdf", stored_name=f"s1_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=False)
    cv2 = CV(candidate_id=cand.id, original_name="c2.pdf", stored_name=f"s2_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=True)
    db.add(cv1); db.add(cv2); db.commit(); db.refresh(cv1); db.refresh(cv2)

    res = client.delete(f"/api/candidate/cvs/{cv2.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204

    db.commit(); db.refresh(cv1); db.refresh(cv2)
    assert cv2.deleted_at is not None
    assert cv2.is_default is False
    assert cv1.is_default is True

def test_delete_last_cv_leaves_no_default(db):
    cand, token = _user(db, "candidate", "cand4")
    cv = CV(candidate_id=cand.id, original_name="last.pdf", stored_name=f"s_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=True)
    db.add(cv); db.commit(); db.refresh(cv)

    res = client.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204
    db.commit(); db.refresh(cv)
    assert cv.deleted_at is not None

    list_res = client.get("/api/candidate/cvs", headers={"Authorization": f"Bearer {token}"})
    assert len(list_res.json()) == 0

def test_cv_limit_5_unblocks_after_soft_delete(db):
    cand, token = _user(db, "candidate", "cand5")
    cv_ids = []
    for i in range(5):
        c = CV(candidate_id=cand.id, original_name=f"c{i}.pdf", stored_name=f"s{i}_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=(i == 0))
        db.add(c); db.commit(); db.refresh(c); cv_ids.append(c.id)

    # Đang 5/5 -> upload file thứ 6 bị 409
    pdf_bytes = b"%PDF-1.4\n" + b"Y" * 1500 + b"\n%%EOF"
    res_block = client.post("/api/candidate/cvs", files={"file": ("new.pdf", pdf_bytes, "application/pdf")}, headers={"Authorization": f"Bearer {token}"})
    assert res_block.status_code == 409

    # Xóa 1 CV
    res_del = client.delete(f"/api/candidate/cvs/{cv_ids[0]}", headers={"Authorization": f"Bearer {token}"})
    assert res_del.status_code == 204

    # Upload lại -> thành công 201
    pdf_bytes2 = b"%PDF-1.4\n" + b"Z" * 1500 + b"\n%%EOF"
    res_ok = client.post("/api/candidate/cvs", files={"file": ("new2.pdf", pdf_bytes2, "application/pdf")}, headers={"Authorization": f"Bearer {token}"})
    assert res_ok.status_code == 201

def test_delete_api_contracts_and_security(db):
    cand_a, token_a = _user(db, "candidate", "cand_a")
    cand_b, token_b = _user(db, "candidate", "cand_b")
    cv = CV(candidate_id=cand_a.id, original_name="cva.pdf", stored_name=f"sa_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=True)
    db.add(cv); db.commit(); db.refresh(cv)

    # 401 khi không đăng nhập
    assert client.delete(f"/api/candidate/cvs/{cv.id}").status_code == 401

    # 403 khi cand B xóa CV của cand A (IDOR)
    res_idor = client.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_idor.status_code == 404  # Trả 404 để không rò rỉ sự tồn tại ID

    # 404 với ID không tồn tại
    assert client.delete("/api/candidate/cvs/999999", headers={"Authorization": f"Bearer {token_a}"}).status_code == 404

    # Xóa lần 1 thành công
    assert client.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token_a}"}).status_code == 204
    # Xóa lần 2 trả 404, không lỗi 500
    res2 = client.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res2.status_code == 404
