"""Integration tests: Đọc file CV từ storage/cvs và uploads/cvs cho Employer & Admin.
Tuân thủ techrecruit-rules: < 200 dòng, dọn dẹp sau test, kiểm tra quyền và đường dẫn.
"""
import os
import uuid
from fastapi.testclient import TestClient
import pytest
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, CV, ApplicationStatus
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.services.cv_service import CV_STORAGE_DIR, LEGACY_UPLOAD_DIR

client = TestClient(app)

@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def _user(db, role, prefix):
    u = User(
        email=f"{prefix}_{uuid.uuid4().hex[:6]}@test.vn",
        password=hash_password("pw123"),
        role=role,
        full_name=f"User_{prefix}",
        is_active=True,
        token_version=1,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u, create_access_token(u.id, u.role, 1)

def _create_cv_file(directory, stored_name, content=None):
    os.makedirs(directory, exist_ok=True)
    p = os.path.join(directory, stored_name)
    with open(p, "wb") as f:
        f.write(content or (b"%PDF-1.4\nTest CV Storage Content\n%%EOF"))
    return p

def test_employer_and_admin_can_read_cv_from_storage_cvs(db):
    """Kiểm tra đọc file CV khi file nằm trong storage/cvs/ (thư mục lưu chuẩn mới)."""
    # 1. Setup user & job
    emp, emp_token = _user(db, "employer", "emp_cv")
    cand, cand_token = _user(db, "candidate", "cand_cv")
    admin, admin_token = _user(db, "admin", "adm_cv")

    cand_profile = CandidateProfile(
        user_id=cand.id,
        public_id=f"cand_pub_{uuid.uuid4().hex[:8]}",
        headline="Frontend Dev",
        is_public=True,
    )
    db.add(cand_profile)

    comp = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", employer_id=emp.id, status="VERIFIED")
    db.add(comp)
    db.commit()
    db.refresh(comp)

    job = Job(
        title="Senior Python Engineer",
        company_id=comp.id,
        employer_id=emp.id,
        status="open",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 2. Tạo file CV trong CV_STORAGE_DIR (storage/cvs/)
    stored_name = f"cv_test_storage_{uuid.uuid4().hex}.pdf"
    file_path = _create_cv_file(CV_STORAGE_DIR, stored_name)

    cv = CV(
        candidate_id=cand.id,
        original_name="Trình Tạo CV Tương Tác A4 _ TechRecruit.pdf",
        stored_name=stored_name,
        mime_type="application/pdf",
        size_bytes=1024,
        is_default=True,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)

    app_record = Application(
        candidate_id=cand.id,
        job_id=job.id,
        cv_id=cv.id,
        cv_name_snapshot=cv.original_name,
        status=ApplicationStatus.SUBMITTED,
    )
    db.add(app_record)
    db.commit()
    db.refresh(app_record)

    try:
        # A. Employer đọc CV từ route /api/employer/applications/{app_id}/cv
        res1 = client.get(
            f"/api/employer/applications/{app_record.id}/cv",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
        assert res1.headers["content-type"] == "application/pdf"
        assert b"%PDF-1.4" in res1.content

        # B. Employer đọc CV từ route /api/employer/candidates/{public_id}/cv/{app_id}
        res2 = client.get(
            f"/api/employer/candidates/{cand_profile.public_id}/cv/{app_record.id}",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
        assert res2.headers["content-type"] == "application/pdf"

        # C. Admin đọc CV từ route /api/admin/applications/{app_id}/cv
        res3 = client.get(
            f"/api/admin/applications/{app_record.id}/cv",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res3.status_code == 200, f"Expected 200, got {res3.status_code}: {res3.text}"

        # D. Admin đọc CV từ route /api/admin/candidate-cvs/{app_id}/file
        res4 = client.get(
            f"/api/admin/candidate-cvs/{app_record.id}/file",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res4.status_code == 200, f"Expected 200, got {res4.status_code}: {res4.text}"

    finally:
        if os.path.isfile(file_path):
            os.remove(file_path)

def test_employer_and_admin_can_read_cv_from_legacy_uploads_cvs(db):
    """Kiểm tra tính tương thích ngược khi file nằm trong uploads/cvs/ (legacy)."""
    emp, emp_token = _user(db, "employer", "emp_leg")
    cand, _ = _user(db, "candidate", "cand_leg")

    comp = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", employer_id=emp.id, status="VERIFIED")
    db.add(comp)
    db.commit()
    db.refresh(comp)

    job = Job(title="Java Dev", company_id=comp.id, employer_id=emp.id, status="open")
    db.add(job)
    db.commit()
    db.refresh(job)

    stored_name = f"cv_test_legacy_{uuid.uuid4().hex}.pdf"
    file_path = _create_cv_file(LEGACY_UPLOAD_DIR, stored_name)

    cv = CV(
        candidate_id=cand.id,
        original_name="Legacy_CV.pdf",
        stored_name=stored_name,
        mime_type="application/pdf",
        size_bytes=1024,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)

    app_record = Application(
        candidate_id=cand.id,
        job_id=job.id,
        cv_id=cv.id,
        cv_name_snapshot=cv.original_name,
        status=ApplicationStatus.SUBMITTED,
    )
    db.add(app_record)
    db.commit()
    db.refresh(app_record)

    try:
        res = client.get(
            f"/api/employer/applications/{app_record.id}/cv",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    finally:
        if os.path.isfile(file_path):
            os.remove(file_path)
