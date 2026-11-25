"""Integration tests for Candidate CVs Management API (<= 200 lines)."""
import io, os, sys, uuid, zipfile, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, CV
from app.models.company import Company
from app.models.job import Job
from app.models.user import User

client = TestClient(app)

def make_docx(entries=None, uncomp_size=None):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", compression=zipfile.ZIP_DEFLATED if uncomp_size else zipfile.ZIP_STORED) as z:
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("word/document.xml", b"0" * (uncomp_size or 1200))
        if entries:
            for i in range(entries): z.writestr(f"word/part_{i}.xml", b"x")
    return b.getvalue()

PDF_B = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n" + b"X" * 1024
DOC_B = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 1024

@pytest.fixture
def db():
    s = SessionLocal()
    try: yield s
    finally: s.close()

def create_user(db, role, name):
    u = User(email=f"{name}_{uuid.uuid4().hex[:6]}@test.com", password=hash_password("pw123"), role=role, full_name=f"User {name}")
    db.add(u); db.commit(); db.refresh(u)
    return u, create_access_token(u.id, u.role, getattr(u, "token_version", 1))

def test_upload_valid_formats_and_metadata(db):
    u, token = create_user(db, "candidate", "valid")
    h = {"Authorization": f"Bearer {token}"}
    r1 = client.post("/api/candidate/cvs", files={"file": ("cv1.pdf", PDF_B + b"1", "application/pdf")}, headers=h)
    assert r1.status_code == 201; d1 = r1.json()
    assert d1["mime"] == "application/pdf" and d1["is_default"] is True and "delete" in d1["allowed_actions"]
    r2 = client.post("/api/candidate/cvs", files={"file": ("cv2.docx", make_docx(), "application/octet-stream")}, headers=h)
    assert r2.status_code == 201 and r2.json()["mime"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    r3 = client.post("/api/candidate/cvs", files={"file": ("cv3.doc", DOC_B, "application/msword")}, headers=h)
    assert r3.status_code == 201 and r3.json()["mime"] == "application/msword"

def test_upload_invalid_and_security(db):
    _, token = create_user(db, "candidate", "sec")
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/candidate/cvs", files={"file": ("fake.pdf", b"<html>Fake</html>", "application/pdf")}, headers=h).status_code == 422
    assert client.post("/api/candidate/cvs", files={"file": ("zero.pdf", b"", "application/pdf")}, headers=h).status_code == 422
    assert client.post("/api/candidate/cvs", files={"file": ("big.pdf", PDF_B + b"0"*(5*1024*1024+1), "application/pdf")}, headers=h).status_code == 422
    bomb = make_docx(uncomp_size=31*1024*1024)
    assert client.post("/api/candidate/cvs", files={"file": ("bomb.docx", bomb, "application/octet-stream")}, headers=h).status_code == 422
    r = client.post("/api/candidate/cvs", files={"file": ("../../CV_Tiếng_Việt_🎯.pdf", PDF_B + b"uni", "application/pdf")}, headers=h)
    assert r.status_code == 201 and "../" not in r.json()["original_name"] and "CV_Tiếng_Việt" in r.json()["original_name"]

def test_duplicate_hash_and_max_limit(db):
    _, token = create_user(db, "candidate", "dup")
    h = {"Authorization": f"Bearer {token}"}
    content = PDF_B + b"unique_hash_dup"
    r1 = client.post("/api/candidate/cvs", files={"file": ("cv_dup1.pdf", content, "application/pdf")}, headers=h)
    assert r1.status_code == 201
    r2 = client.post("/api/candidate/cvs", files={"file": ("cv_dup2.pdf", content, "application/pdf")}, headers=h)
    assert r2.status_code == 409 and "CV này đã được tải lên" in r2.json()["detail"]
    for i in range(2, 6):
        res = client.post("/api/candidate/cvs", files={"file": (f"cv_{i}.pdf", PDF_B + f"uniq_{i}".encode(), "application/pdf")}, headers=h)
        assert res.status_code == 201
    r6 = client.post("/api/candidate/cvs", files={"file": ("cv6.pdf", PDF_B + b"cv6_bytes", "application/pdf")}, headers=h)
    assert r6.status_code == 409 and "tối đa 5 CV" in r6.json()["detail"]

def test_role_and_isolation(db):
    _, temp = create_user(db, "employer", "emp")
    assert client.get("/api/candidate/cvs", headers={"Authorization": f"Bearer {temp}"}).status_code == 403
    _, t1 = create_user(db, "candidate", "cand_a")
    _, t2 = create_user(db, "candidate", "cand_b")
    r1 = client.post("/api/candidate/cvs", files={"file": ("a.pdf", PDF_B + b"a", "application/pdf")}, headers={"Authorization": f"Bearer {t1}"})
    cv_id = r1.json()["id"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.get(f"/api/candidate/cvs/{cv_id}/file", headers=h2).status_code == 404
    assert client.patch(f"/api/candidate/cvs/{cv_id}", json={"name": "hacked.pdf"}, headers=h2).status_code == 404
    assert client.delete(f"/api/candidate/cvs/{cv_id}", headers=h2).status_code == 404

def test_idempotency_key(db):
    _, token = create_user(db, "candidate", "idem")
    h = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"key_{uuid.uuid4().hex}"}
    cnt = PDF_B + b"idempotent_test"
    r1 = client.post("/api/candidate/cvs", files={"file": ("idem.pdf", cnt, "application/pdf")}, headers=h)
    assert r1.status_code == 201
    r2 = client.post("/api/candidate/cvs", files={"file": ("idem.pdf", cnt, "application/pdf")}, headers=h)
    assert r2.status_code == 201 and r2.json()["id"] == r1.json()["id"]

def test_file_headers_and_storage_path(db):
    _, token = create_user(db, "candidate", "headers")
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/candidate/cvs", files={"file": ("hd.pdf", PDF_B + b"hd", "application/pdf")}, headers=h)
    cv_id = r.json()["id"]
    res = client.get(f"/api/candidate/cvs/{cv_id}/file", headers=h)
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert "no-store" in res.headers.get("cache-control", "")
    assert "inline" in res.headers.get("content-disposition", "")
    assert "storage" in settings.CV_UPLOAD_DIR and not settings.CV_UPLOAD_DIR.startswith("uploads")

def test_delete_active_cv_and_reassign_default(db):
    c, token = create_user(db, "candidate", "del_active")
    emp, _ = create_user(db, "employer", "emp_del")
    h = {"Authorization": f"Bearer {token}"}
    r1 = client.post("/api/candidate/cvs", files={"file": ("cv1.pdf", PDF_B + b"c1", "application/pdf")}, headers=h)
    cv1_id = r1.json()["id"]
    r2 = client.post("/api/candidate/cvs", files={"file": ("cv2.pdf", PDF_B + b"c2", "application/pdf")}, headers=h)
    cv2_id = r2.json()["id"]
    cmp = db.scalar(select(Company).limit(1))
    job = Job(title="Protect Active CV Job", company_id=cmp.id if cmp else 1, employer_id=emp.id)
    db.add(job); db.commit(); db.refresh(job)
    app_record = Application(job_id=job.id, candidate_id=c.id, cv_id=cv1_id, cv_name_snapshot="cv1.pdf", status="REVIEWING")
    db.add(app_record); db.commit()
    del_res = client.delete(f"/api/candidate/cvs/{cv1_id}", headers=h)
    assert del_res.status_code == 204
    # CV bị xóa mềm, danh sách ứng viên chỉ còn cv2 và cv2 được tự động gán mặc định
    list_res = client.get("/api/candidate/cvs", headers=h).json()
    assert len(list_res) == 1 and list_res[0]["id"] == cv2_id and list_res[0]["is_default"] is True
