"""Tests cho Tác vụ 1 (sort jobs), Tác vụ 2 (company verification metadata) và Tác vụ 3 (tiêu chí xác thực NTD)."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.candidate import CandidateProfile
from app.models.company import Company, CompanyStatus
from app.models.company_verification import CompanyVerification
from app.models.job import Job
from app.models.report import Report, ReportStatus
from app.models.user import User

client = TestClient(app)


def _mk_user(db, role: str, domain: str = "testcorp.vn", created_at: datetime | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    u = User(
        email=f"u_{uid}@{domain}",
        password=hash_password("Test@1234"),
        full_name=f"User {uid}",
        role=role,
        is_active=True,
        created_at=created_at or datetime.now(),
    )
    db.add(u)
    db.flush()
    return u


def _cleanup(db, *, user_ids: list[int], comp_ids: list[int], job_ids: list[int], report_ids: list[int]):
    db.rollback()
    if report_ids:
        db.query(Report).filter(Report.id.in_(report_ids)).delete(synchronize_session=False)
    if job_ids:
        db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
    if comp_ids:
        db.query(AuditLog).filter(AuditLog.target_type == "employer_criterion", AuditLog.target_id.in_(comp_ids)).delete(synchronize_session=False)
        db.query(CompanyVerification).filter(CompanyVerification.company_id.in_(comp_ids)).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_(comp_ids)).delete(synchronize_session=False)
    if user_ids:
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


def test_public_jobs_sort_salary_and_relevant():
    db = SessionLocal()
    u_ids, c_ids, j_ids = [], [], []
    try:
        cand = _mk_user(db, "candidate", "gmail.com")
        u_ids.append(cand.id)
        db.add(CandidateProfile(user_id=cand.id, skills_json=json.dumps(["Python", "FastAPI", "Docker"]), level="Senior"))
        emp = _mk_user(db, "employer", "sortco.vn")
        u_ids.append(emp.id)
        comp = Company(name="SortCo Test", slug=f"sortco-{uuid.uuid4().hex[:6]}", employer_id=emp.id, owner_id=emp.id, status=CompanyStatus.VERIFIED, is_visible=True, is_draft=False)
        db.add(comp)
        db.flush()
        c_ids.append(comp.id)
        j_neg = Job(title="Neg Job", employer_id=emp.id, company_id=comp.id, status="published", is_salary_negotiable=True, skills=["Python"])
        j_hi = Job(title="High Job", employer_id=emp.id, company_id=comp.id, status="published", salary_min=50000000, salary_max=99000000, skills=["Go"])
        j_fit = Job(title="Fit Job", employer_id=emp.id, company_id=comp.id, status="published", salary_min=20000000, salary_max=25000000, level="Senior", skills=["Python", "FastAPI", "Docker"])
        db.add_all([j_neg, j_hi, j_fit])
        db.flush()
        j_ids.extend([j_neg.id, j_hi.id, j_fit.id])
        db.commit()

        r_sal = client.get(f"/api/jobs?company={comp.slug}&sort=salary_desc").json()["items"]
        assert [x["id"] for x in r_sal] == [j_hi.id, j_fit.id, j_neg.id]

        tok = create_access_token(cand.id, "candidate", 1)
        r_rel = client.get(f"/api/jobs?company={comp.slug}&sort=relevant", headers={"Authorization": f"Bearer {tok}"}).json()["items"]
        assert r_rel[0]["id"] == j_fit.id
        assert r_rel[0]["match_score"] >= r_rel[1]["match_score"]
    finally:
        _cleanup(db, user_ids=u_ids, comp_ids=c_ids, job_ids=j_ids, report_ids=[])
        db.close()


def test_company_detail_verification_date_real():
    db = SessionLocal()
    u_ids, c_ids = [], []
    try:
        emp = _mk_user(db, "employer", "vco.vn")
        u_ids.append(emp.id)
        slug = f"vco-{uuid.uuid4().hex[:6]}"
        comp = Company(name="VerifCo Test", slug=slug, employer_id=emp.id, owner_id=emp.id, status=CompanyStatus.VERIFIED, verification_status="da_xac_minh", is_verified=True, verified_at=datetime(2026, 11, 15, 10, 0, 0), is_visible=True, is_draft=False)
        db.add(comp)
        db.commit()
        c_ids.append(comp.id)
        res = client.get(f"/api/companies/{slug}")
        assert res.status_code == 200
        body = res.json()
        assert body["verification_status"] == "da_xac_minh"
        assert body["verified_at"].startswith("2026-11-15")
    finally:
        _cleanup(db, user_ids=u_ids, comp_ids=c_ids, job_ids=[], report_ids=[])
        db.close()


def test_employer_criteria_permissions_and_manual_approve():
    db = SessionLocal()
    u_ids, c_ids, r_ids = [], [], []
    try:
        emp1 = _mk_user(db, "employer", "gmail.com", created_at=datetime.now() - timedelta(days=20))
        emp2 = _mk_user(db, "employer", "vnptit.vn", created_at=datetime.now() - timedelta(days=200))
        adm = _mk_user(db, "admin", "admin.vn")
        cand = _mk_user(db, "candidate", "gmail.com")
        u_ids.extend([emp1.id, emp2.id, adm.id, cand.id])

        c1 = Company(name="NoSite Co", slug=f"nosite-{uuid.uuid4().hex[:6]}", employer_id=emp1.id, owner_id=emp1.id, website=None, status=CompanyStatus.PENDING, is_draft=True)
        c2 = Company(name="OldSite Co", slug=f"oldsite-{uuid.uuid4().hex[:6]}", employer_id=emp2.id, owner_id=emp2.id, website="https://vnptit.vn", status=CompanyStatus.VERIFIED, is_verified=True, verification_status="da_xac_minh", is_draft=False)
        db.add_all([c1, c2])
        db.flush()
        c_ids.extend([c1.id, c2.id])

        rep = Report(reporter_id=cand.id, post_id=0, employer_id=emp1.id, reason="Spam tin", status=ReportStatus.PENDING)
        db.add(rep)
        db.commit()
        r_ids.append(rep.id)

        t_emp1 = create_access_token(emp1.id, "employer", 1)
        t_cand = create_access_token(cand.id, "candidate", 1)
        t_adm = create_access_token(adm.id, "admin", 1)

        assert client.get("/api/employer/verification-criteria", headers={"Authorization": f"Bearer {t_cand}"}).status_code == 403
        assert client.get(f"/api/employer/companies/{c2.id}/verification-criteria", headers={"Authorization": f"Bearer {t_emp1}"}).status_code == 403
        assert client.post(f"/api/admin/companies/{c1.id}/criteria/account_age/approve", json={"reason": "Hop le du chung tu"}, headers={"Authorization": f"Bearer {t_emp1}"}).status_code == 403

        data1 = client.get("/api/employer/verification-criteria", headers={"Authorization": f"Bearer {t_emp1}"}).json()
        cmap1 = {x["code"]: x for x in data1["criteria"]}
        assert cmap1["domain_email"]["status"] == "chua_kiem_tra"
        assert cmap1["account_age"]["status"] == "chua_dat"
        assert "160" in cmap1["account_age"]["action_hint"] or "159" in cmap1["account_age"]["action_hint"]
        assert cmap1["no_open_reports"]["status"] == "chua_dat"
        assert cmap1["phone_verified"]["status"] == "chua_kiem_tra"

        adm_list = client.get("/api/admin/company-verifications?has_open_reports=true", headers={"Authorization": f"Bearer {t_adm}"}).json()
        assert any(it["id"] == c1.id for it in adm_list["items"])
        assert all(it["id"] != c2.id for it in adm_list["items"])

        assert client.post(f"/api/admin/companies/{c1.id}/criteria/account_age/approve", json={"reason": ""}, headers={"Authorization": f"Bearer {t_adm}"}).status_code == 400
        ok = client.post(f"/api/admin/companies/{c1.id}/criteria/account_age/approve", json={"reason": "Đã xác minh giấy phép kinh doanh trực tiếp"}, headers={"Authorization": f"Bearer {t_adm}"})
        assert ok.status_code == 200
        body = ok.json()
        assert next(x for x in body["criteria"] if x["code"] == "account_age")["status"] == "dat"
        assert len(body["logs"]) == 1
        assert body["logs"][0]["actor_id"] == adm.id
    finally:
        _cleanup(db, user_ids=u_ids, comp_ids=c_ids, job_ids=[], report_ids=r_ids)
        db.close()
