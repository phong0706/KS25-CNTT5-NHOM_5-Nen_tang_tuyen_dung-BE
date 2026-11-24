"""Pytest kiểm chứng cách ly dữ liệu theo company_id trên Employer Dashboard & APIs (<= 195 dòng)."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys, uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, ApplicationNote, ApplicationStatus, Interview
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.user import User


def _mk_user(db, prefix: str, role: str) -> User:
    u = User(
        email=f"{prefix}_{uuid.uuid4().hex[:6]}@test-iso.local",
        password=hash_password("TestPass123!"),
        full_name=f"User {prefix}",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    db.flush()
    return u


def _mk_comp(db, owner: User, name: str, verified: bool = True) -> Company:
    c = Company(
        name=name,
        slug=f"test-iso-{uuid.uuid4().hex[:8]}",
        employer_id=owner.id,
        owner_id=owner.id,
        status=CompanyStatus.VERIFIED if verified else CompanyStatus.PENDING,
        verification_status="da_xac_minh" if verified else "chua_xac_minh",
        is_verified=verified,
        is_visible=True,
        is_draft=False,
    )
    db.add(c)
    db.flush()
    return c


def _mk_job(db, owner: User, comp: Company, title: str, st: str, deadline: date | None = None) -> Job:
    j = Job(
        employer_id=owner.id,
        company_id=comp.id,
        title=title,
        level="Middle",
        work_type="Full-time",
        location="Hà Nội",
        quantity=1,
        deadline=deadline or (date.today() + timedelta(days=20)),
        description="Mô tả công việc kiểm thử cách ly dữ liệu.",
        requirements="Yêu cầu kinh nghiệm kiểm thử.",
        skills=["Python"],
        is_salary_negotiable=True,
        status=st,
        published_at=datetime.now(timezone.utc) if st == "published" else None,
    )
    db.add(j)
    db.flush()
    return j


@pytest.fixture(scope="module")
def env():
    db = SessionLocal()
    client = TestClient(app)
    created_users, created_comps, created_jobs, created_apps = [], [], [], []
    try:
        emp_a = _mk_user(db, "emp_a", "employer")
        emp_b = _mk_user(db, "emp_b", "employer")
        emp_nocomp = _mk_user(db, "emp_nc", "employer")
        emp_unverif = _mk_user(db, "emp_uv", "employer")
        cand = _mk_user(db, "cand", "candidate")
        adm = _mk_user(db, "adm", "admin")
        created_users.extend([emp_a, emp_b, emp_nocomp, emp_unverif, cand, adm])

        comp_a = _mk_comp(db, emp_a, "Test Sao Khue Iso", True)
        comp_b = _mk_comp(db, emp_b, "Test Xanh Lam Iso", True)
        comp_uv = _mk_comp(db, emp_unverif, "Test Unverified Iso", False)
        created_comps.extend([comp_a, comp_b, comp_uv])

        # A: 2 published (1 expired), 1 draft, 1 pending, 1 closed -> open_jobs=2
        ja1 = _mk_job(db, emp_a, comp_a, "A Open 1", "published")
        ja2 = _mk_job(db, emp_a, comp_a, "A Open 2", "published")
        ja_exp = _mk_job(db, emp_a, comp_a, "A Expired", "published", date.today() - timedelta(days=2))
        ja_draft = _mk_job(db, emp_a, comp_a, "A Draft", "draft")
        ja_pend = _mk_job(db, emp_a, comp_a, "A Pending", "pending")
        ja_closed = _mk_job(db, emp_a, comp_a, "A Closed", "closed")
        # B: 1 published (cố tình gán employer_id=emp_a để test không rò chéo!)
        jb1 = _mk_job(db, emp_a, comp_b, "B Open CrossEid", "published")
        created_jobs.extend([ja1, ja2, ja_exp, ja_draft, ja_pend, ja_closed, jb1])

        app_a = Application(candidate_id=cand.id, job_id=ja1.id, cv_name_snapshot="a.pdf", status=ApplicationStatus.SUBMITTED.value)
        app_b = Application(candidate_id=cand.id, job_id=jb1.id, cv_name_snapshot="b.pdf", status=ApplicationStatus.SUBMITTED.value)
        db.add_all([app_a, app_b])
        db.flush()
        created_apps.extend([app_a, app_b])

        db.add(ApplicationNote(application_id=app_b.id, author_id=emp_b.id, content="Note B secret"))
        iv_b = Interview(
            application_id=app_b.id,
            scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3),
            duration_min=30, mode="Online", status="scheduled", created_by=emp_b.id,
        )
        db.add(iv_b)
        db.commit()

        yield {
            "db": db, "client": client,
            "tok_a": create_access_token(emp_a.id, "employer"),
            "tok_b": create_access_token(emp_b.id, "employer"),
            "tok_nc": create_access_token(emp_nocomp.id, "employer"),
            "tok_uv": create_access_token(emp_unverif.id, "employer"),
            "tok_cand": create_access_token(cand.id, "candidate"),
            "tok_adm": create_access_token(adm.id, "admin"),
            "comp_a": comp_a, "comp_b": comp_b,
            "ja1": ja1, "ja2": ja2, "ja_exp": ja_exp, "jb1": jb1,
            "app_a": app_a, "app_b": app_b, "iv_b": iv_b, "adm": adm,
        }
    finally:
        for ap in created_apps:
            db.query(Interview).filter(Interview.application_id == ap.id).delete()
            db.query(ApplicationNote).filter(ApplicationNote.application_id == ap.id).delete()
            db.query(Application).filter(Application.id == ap.id).delete()
        for j in created_jobs:
            db.query(Job).filter(Job.id == j.id).delete()
        for c in created_comps:
            db.query(AuditLog).filter(AuditLog.target_type == "company", AuditLog.target_id == c.id).delete()
            db.query(Company).filter(Company.id == c.id).delete()
        for u in created_users:
            db.query(User).filter(User.id == u.id).delete()
        db.commit()
        db.close()


def test_auth_and_scope_errors(env):
    c = env["client"]
    assert c.get("/api/employer/dashboard").status_code == 401
    assert c.get("/api/employer/dashboard", headers={"Authorization": f"Bearer {env['tok_cand']}"}).status_code == 403
    assert c.get("/api/employer/dashboard", headers={"Authorization": f"Bearer {env['tok_nc']}"}).status_code == 409
    assert c.get("/api/employer/dashboard", headers={"Authorization": f"Bearer {env['tok_uv']}"}).status_code == 409


def test_dashboard_matches_all_views_and_tabs(env):
    c, ha = env["client"], {"Authorization": f"Bearer {env['tok_a']}"}
    dash = c.get("/api/employer/dashboard", headers=ha).json()
    assert dash["open_jobs"] == 2  # ja_exp hết hạn không được tính!
    assert dash["draft_jobs"] == 1
    assert dash["pending_jobs"] == 1
    assert dash["closed_jobs"] == 1
    assert dash["applications_total"] == 1
    assert dash["applications_unseen"] == 1
    assert dash["interviews_upcoming"]["count"] == 0
    assert dash["company"]["review_status"] == "da_xac_minh"

    emp_pub = c.get("/api/employer/jobs?status=published", headers=ha).json()
    emp_all = c.get("/api/employer/jobs", headers=ha).json()
    pub_comp = c.get(f"/api/companies/{env['comp_a'].slug}").json()
    pub_jobs = c.get(f"/api/jobs?company={env['comp_a'].slug}").json()

    assert dash["open_jobs"] == emp_pub["pagination"]["total_items"] == pub_comp["open_jobs"] == pub_jobs["total"] == 2
    assert emp_all["counts"]["draft"] + emp_all["counts"]["pending"] + emp_all["counts"]["closed"] + 3 == emp_all["counts"]["all"]


def test_cross_company_isolation_returns_404(env):
    c, ha = env["client"], {"Authorization": f"Bearer {env['tok_a']}"}
    jb1_id, app_b_id, iv_b_id = env["jb1"].id, env["app_b"].id, env["iv_b"].id
    assert c.get(f"/api/employer/jobs/{jb1_id}", headers=ha).status_code == 404
    assert c.patch(f"/api/employer/jobs/{jb1_id}/status", json={"action": "close"}, headers=ha).status_code == 404
    assert c.delete(f"/api/employer/jobs/{jb1_id}", headers=ha).status_code == 404
    assert c.get(f"/api/employer/applications/{app_b_id}", headers=ha).status_code == 404
    assert c.get(f"/api/employer/applications/{app_b_id}/cv", headers=ha).status_code == 404
    assert c.get(f"/api/employer/applications/{app_b_id}/notes", headers=ha).status_code == 404
    assert c.post(f"/api/employer/applications/{app_b_id}/notes", json={"content": "hack"}, headers=ha).status_code == 404
    assert c.patch(f"/api/employer/applications/{app_b_id}/status", json={"status": "REVIEWING"}, headers=ha).status_code == 404
    assert c.post(f"/api/employer/interviews/{iv_b_id}/cancel", json={"reason": "hack"}, headers=ha).status_code == 404


def test_admin_mode_creates_audit_log_and_job_mutations_update_counts(env):
    c, db = env["client"], env["db"]
    ha = {"Authorization": f"Bearer {env['tok_a']}"}
    hadm = {"Authorization": f"Bearer {env['tok_adm']}"}

    r_adm = c.get(f"/api/employer/dashboard/admin?company_id={env['comp_b'].id}", headers=hadm)
    assert r_adm.status_code == 200
    assert r_adm.json()["open_jobs"] == 1
    db.commit()
    log_row = db.scalar(select(AuditLog).where(AuditLog.target_id == env["comp_b"].id, AuditLog.action == "view_employer_dashboard"))
    assert log_row is not None

    # Tạo tin mới pending -> admin duyệt -> open_jobs tăng 1; đóng tin -> open_jobs giảm 1 và closed_jobs tăng 1
    r_new = c.post("/api/employer/jobs", json={
        "title": "New Live Job", "level": "Middle", "work_type": "Full-time", "location": "Hà Nội",
        "quantity": 1, "deadline": str(date.today() + timedelta(days=10)),
        "description": "Mô tả đủ dài cho tin mới.", "requirements": "Yêu cầu đủ dài.",
        "skills": ["Python"], "is_salary_negotiable": True, "benefits": [], "status": "pending",
    }, headers=ha)
    assert r_new.status_code == 201
    new_id = r_new.json()["id"]
    try:
        r_app = c.post(f"/api/admin/jobs/{new_id}/approve", json={"version": 1}, headers=hadm)
        assert r_app.status_code == 200
        assert c.get("/api/employer/dashboard", headers=ha).json()["open_jobs"] == 3
        assert c.patch(f"/api/employer/jobs/{new_id}/status", json={"action": "close"}, headers=ha).status_code == 200
        after_close = c.get("/api/employer/dashboard", headers=ha).json()
        assert after_close["open_jobs"] == 2
        assert after_close["closed_jobs"] == 2
    finally:
        from app.models.job_status_history import JobStatusHistory
        from app.models.notification import Notification
        db.query(JobStatusHistory).filter(JobStatusHistory.job_id == new_id).delete()
        db.query(Notification).filter(Notification.ref_id == new_id).delete()
        db.query(Job).filter(Job.id == new_id).delete()
        db.commit()
