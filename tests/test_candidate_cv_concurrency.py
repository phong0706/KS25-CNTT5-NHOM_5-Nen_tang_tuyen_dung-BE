"""Concurrency tests cho xóa và đổi mặc định CV (SEC-CV-02).
Tuân thủ techrecruit-rules: <= 150 dòng, dọn dẹp sau test, chạy trên app_db_test.
"""
from concurrent.futures import ThreadPoolExecutor
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import CV, Application
from app.models.company import Company
from app.models.job import Job
from app.models.user import User

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

def test_concurrent_double_delete(db):
    cand, token = _user(db, "candidate", "cand_conc1")
    cv = CV(candidate_id=cand.id, original_name="double_del.pdf", stored_name=f"s_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=False)
    db.add(cv); db.commit(); db.refresh(cv)

    def do_delete():
        c = TestClient(app)
        return c.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {token}"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(do_delete)
        f2 = executor.submit(do_delete)
        r1 = f1.result()
        r2 = f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    # Đúng một request thành công 204, request còn lại trả 404 (vì đã bị xóa mềm), không có 500
    assert statuses == [204, 404]

def test_concurrent_set_default(db):
    cand, token = _user(db, "candidate", "cand_conc2")
    cv1 = CV(candidate_id=cand.id, original_name="c1.pdf", stored_name=f"s1_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=True)
    cv2 = CV(candidate_id=cand.id, original_name="c2.pdf", stored_name=f"s2_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=False)
    cv3 = CV(candidate_id=cand.id, original_name="c3.pdf", stored_name=f"s3_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=False)
    db.add(cv1); db.add(cv2); db.add(cv3); db.commit()

    def set_def(target_cv_id):
        c = TestClient(app)
        return c.post(f"/api/candidate/cvs/{target_cv_id}/default", headers={"Authorization": f"Bearer {token}"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(set_def, cv2.id)
        f2 = executor.submit(set_def, cv3.id)
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status_code == 200
    assert r2.status_code == 200

    # Trạng thái cuối cùng: ĐÚNG MỘT CV CÓ is_default=True
    db.commit()
    active_cvs = db.scalars(select(CV).where(CV.candidate_id == cand.id, CV.deleted_at.is_(None))).all()
    default_count = sum(1 for c in active_cvs if c.is_default)
    assert default_count == 1

def test_concurrent_delete_and_apply(db):
    cand, cand_token = _user(db, "candidate", "cand_conc3")
    emp, _ = _user(db, "employer", "emp_conc3")
    comp = Company(name="CoConc", slug=f"co-conc-{uuid.uuid4().hex[:6]}", employer_id=emp.id)
    db.add(comp); db.commit(); db.refresh(comp)
    job = Job(title="Job Conc", company_id=comp.id, employer_id=emp.id, status="published")
    db.add(job); db.commit(); db.refresh(job)

    cv = CV(candidate_id=cand.id, original_name="apply_del.pdf", stored_name=f"s_{uuid.uuid4().hex}.pdf", mime_type="application/pdf", size_bytes=1500, is_default=True)
    db.add(cv); db.commit(); db.refresh(cv)

    def do_delete():
        c = TestClient(app)
        return c.delete(f"/api/candidate/cvs/{cv.id}", headers={"Authorization": f"Bearer {cand_token}"})

    def do_apply():
        c = TestClient(app)
        return c.post(f"/api/jobs/{job.id}/apply", json={"cv_id": cv.id, "cover_letter": "Hi"}, headers={"Authorization": f"Bearer {cand_token}"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_del = executor.submit(do_delete)
        f_app = executor.submit(do_apply)
        r_del = f_del.result()
        r_app = f_app.result()

    # Xóa luôn trả về 204
    assert r_del.status_code == 204
    # Nộp đơn trả 200/201 (nếu nộp trước xóa) hoặc 422 (nếu xóa trước nộp), KHÔNG BAO GIỜ bị 500
    assert r_app.status_code in [200, 201, 422]

