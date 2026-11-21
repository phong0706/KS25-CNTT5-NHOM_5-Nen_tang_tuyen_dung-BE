"""Integration tests: Phép so khớp, CV download, Rate limiting, Fuzzing & Debounce views (SEC-02).
Tuân thủ techrecruit-rules: < 200 dòng, dọn dẹp dữ liệu, test độc lập.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
import pytest

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, ApplicationStatus, CV
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.services.profile_access import profile_view_rate_limiter

client = TestClient(app)
CV_DIR = Path(__file__).resolve().parent.parent / "uploads" / "cvs"
CV_DIR.mkdir(parents=True, exist_ok=True)

@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def _u(db, role, name):
    u = User(email=f"{name}_{uuid.uuid4().hex[:6]}@t.vn", password=hash_password("pw123"), role=role, full_name=f"U_{name}", is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u, create_access_token(u.id, u.role, getattr(u, "token_version", 1))

def test_job_id_validation_and_matching(db):
    cand_u, _ = _u(db, "candidate", "mcand")
    prof = CandidateProfile(user_id=cand_u.id, public_id=f"pub_{uuid.uuid4().hex[:18]}", is_public=True, skills_json=json.dumps(["Python", "FastAPI"]))
    db.add(prof); db.commit(); db.refresh(prof)
    emp_a, emp_a_t = _u(db, "employer", "mempa")
    comp_a = Company(name="CmpA", slug=f"ca-{uuid.uuid4().hex[:6]}", employer_id=emp_a.id)
    db.add(comp_a); db.commit(); db.refresh(comp_a)
    job_a = Job(title="Backend Dev", company_id=comp_a.id, employer_id=emp_a.id, status="published", level="middle")
    db.add(job_a); db.commit(); db.refresh(job_a)
    emp_other, _ = _u(db, "employer", "mempother")
    comp_other = Company(name="CmpO", slug=f"co-{uuid.uuid4().hex[:6]}", employer_id=emp_other.id)
    db.add(comp_other); db.commit(); db.refresh(comp_other)
    job_other = Job(title="Other Job", company_id=comp_other.id, employer_id=emp_other.id, status="published")
    db.add(job_other); db.commit(); db.refresh(job_other)

    # 1. job_id không thuộc employer -> 404
    h = {"Authorization": f"Bearer {emp_a_t}"}
    r_bad = client.get(f"/api/employer/candidates/{prof.public_id}?job_id={job_other.id}", headers=h)
    assert r_bad.status_code == 404

    # 2. job_id hợp lệ thuộc employer -> 200 kèm block match
    r_ok = client.get(f"/api/employer/candidates/{prof.public_id}?job_id={job_a.id}", headers=h)
    assert r_ok.status_code == 200
    d = r_ok.json()
    assert "match" in d
    assert "score" in d["match"]
    assert "matched_skills" in d["match"]
    assert "missing_skills" in d["match"]

def test_cv_download_matrix(db):
    cand_u, _ = _u(db, "candidate", "cvcand")
    prof = CandidateProfile(user_id=cand_u.id, public_id=f"pub_{uuid.uuid4().hex[:18]}", is_public=True)
    db.add(prof); db.commit(); db.refresh(prof)
    emp_a, emp_a_t = _u(db, "employer", "cvempa")
    comp_a = Company(name="CvA", slug=f"cva-{uuid.uuid4().hex[:6]}", employer_id=emp_a.id)
    db.add(comp_a); db.commit(); db.refresh(comp_a)
    job_a = Job(title="Job CV", company_id=comp_a.id, employer_id=emp_a.id, status="published")
    db.add(job_a); db.commit(); db.refresh(job_a)

    stored_fn = f"test_cv_{uuid.uuid4().hex}.pdf"
    (CV_DIR / stored_fn).write_bytes(b"%PDF-1.4 sample cv content")
    cv_record = CV(candidate_id=cand_u.id, stored_name=stored_fn, original_name="MyCV.pdf", mime_type="application/pdf")
    db.add(cv_record); db.commit(); db.refresh(cv_record)

    app_a = Application(candidate_id=cand_u.id, job_id=job_a.id, status="SUBMITTED", cv_id=cv_record.id)
    db.add(app_a); db.commit(); db.refresh(app_a)

    emp_b, emp_b_t = _u(db, "employer", "cvempb")
    # 1. Tải CV đúng application của mình -> 200
    r_ok = client.get(f"/api/employer/candidates/{prof.public_id}/cv/{app_a.id}", headers={"Authorization": f"Bearer {emp_a_t}"})
    assert r_ok.status_code == 200
    assert r_ok.headers.get("x-content-type-options") == "nosniff"

    # 2. Employer khác tải -> 404
    r_b = client.get(f"/api/employer/candidates/{prof.public_id}/cv/{app_a.id}", headers={"Authorization": f"Bearer {emp_b_t}"})
    assert r_b.status_code == 404

    # 3. Application đã rút -> 404
    app_a.status = ApplicationStatus.WITHDRAWN.value
    app_a.withdrawn_at = datetime.now(timezone.utc)
    db.commit()
    r_withdrawn = client.get(f"/api/employer/candidates/{prof.public_id}/cv/{app_a.id}", headers={"Authorization": f"Bearer {emp_a_t}"})
    assert r_withdrawn.status_code == 404

def test_rate_limiting_60_req_per_minute(db):
    profile_view_rate_limiter.clear()
    cand_u, _ = _u(db, "candidate", "rlcand")
    prof = CandidateProfile(user_id=cand_u.id, public_id=f"pub_{uuid.uuid4().hex[:18]}", is_public=True)
    db.add(prof); db.commit(); db.refresh(prof)
    emp_u, emp_t = _u(db, "employer", "rlemp")

    h = {"Authorization": f"Bearer {emp_t}"}
    for _ in range(60):
        res = client.get(f"/api/employer/candidates/{prof.public_id}", headers=h)
        assert res.status_code == 200

    # Lần thứ 61 -> 429
    res_61 = client.get(f"/api/employer/candidates/{prof.public_id}", headers=h)
    assert res_61.status_code == 429
    assert "Retry-After" in res_61.headers
    profile_view_rate_limiter.clear()

def test_fuzz_public_id_safety(db):
    emp_u, emp_t = _u(db, "employer", "fzemp")
    h = {"Authorization": f"Bearer {emp_t}"}
    fuzz_payloads = [
        "123", "' OR '1'='1", "pub_<img src=x onerror=alert(1)>",
        "a" * 200, "pub_traversal_.._.._passwd", "pub_special_chars_%2A%26%21",
    ]
    for p in fuzz_payloads:
        r = client.get(f"/api/employer/candidates/{p}", headers=h)
        assert r.status_code == 404
        assert r.json() == {"detail": "Hồ sơ ứng viên không tồn tại hoặc không khả dụng."}

def test_views_summary_and_debounce(db):
    cand_u, cand_t = _u(db, "candidate", "vwcand")
    prof = CandidateProfile(user_id=cand_u.id, public_id=f"pub_{uuid.uuid4().hex[:18]}", is_public=True)
    db.add(prof); db.commit(); db.refresh(prof)
    emp_1, emp_1_t = _u(db, "employer", "vwemp1")
    emp_2, emp_2_t = _u(db, "employer", "vwemp2")

    ch = {"Authorization": f"Bearer {cand_t}"}
    base_views = client.get("/api/candidate/profile/views-summary", headers=ch).json()["views_30d"]

    # Employer 1 xem lần 1 -> views tăng 1
    client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_1_t}"})
    v1 = client.get("/api/candidate/profile/views-summary", headers=ch).json()["views_30d"]
    assert v1 == base_views + 1

    # Employer 1 xem lại ngay (trong 30 phút) -> debounce không tăng
    client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_1_t}"})
    v2 = client.get("/api/candidate/profile/views-summary", headers=ch).json()["views_30d"]
    assert v2 == v1

    # Employer 2 xem -> views tăng tiếp 1
    client.get(f"/api/employer/candidates/{prof.public_id}", headers={"Authorization": f"Bearer {emp_2_t}"})
    v3 = client.get("/api/candidate/profile/views-summary", headers=ch).json()["views_30d"]
    assert v3 == v1 + 1
