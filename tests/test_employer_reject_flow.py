"""Pytest kiểm thử luồng Từ chối hồ sơ ứng viên & Từ chối hàng loạt (<= 195 dòng)."""
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
from app.models.application import (
    Application, ApplicationNote, ApplicationStatus, ApplicationStatusHistory,
    Interview, MetaRejectionReason,
)
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User


def _mk_user(db, pfx: str, role: str) -> User:
    u = User(
        email=f"{pfx}_{uuid.uuid4().hex[:6]}@test-rej.local",
        password=hash_password("TestPass123!"), full_name=f"Test {pfx}",
        role=role, is_active=True, is_verified=True,
    )
    db.add(u); db.flush()
    return u


def _mk_comp(db, owner: User) -> Company:
    c = Company(
        name=f"Comp {uuid.uuid4().hex[:6]}", slug=f"comp-rej-{uuid.uuid4().hex[:6]}",
        employer_id=owner.id, owner_id=owner.id, status=CompanyStatus.VERIFIED,
        verification_status="da_xac_minh", is_verified=True, is_visible=True, is_draft=False,
    )
    db.add(c); db.flush()
    return c


def _mk_job(db, owner: User, comp: Company) -> Job:
    j = Job(
        employer_id=owner.id, company_id=comp.id, title="Backend Test Rej",
        level="Middle", work_type="Full-time", location="Hà Nội", quantity=1,
        deadline=date.today() + timedelta(days=15), description="Desc", requirements="Req",
        skills=["Python"], is_salary_negotiable=True, status="published",
        published_at=datetime.now(timezone.utc),
    )
    db.add(j); db.flush()
    return j


@pytest.fixture(scope="module")
def rej_env():
    db = SessionLocal()
    client = TestClient(app)
    users, comps, jobs, apps = [], [], [], []
    try:
        emp_a = _mk_user(db, "ea", "employer")
        emp_b = _mk_user(db, "eb", "employer")
        cand = _mk_user(db, "ca", "candidate")
        users.extend([emp_a, emp_b, cand])
        comp_a = _mk_comp(db, emp_a)
        comp_b = _mk_comp(db, emp_b)
        comps.extend([comp_a, comp_b])
        ja = _mk_job(db, emp_a, comp_a)
        jb = _mk_job(db, emp_b, comp_b)
        jobs.extend([ja, jb])

        reason = db.scalar(select(MetaRejectionReason).order_by(MetaRejectionReason.id.asc()))
        if not reason:
            reason = MetaRejectionReason(slug="khong-dat-chuyen-mon", name="Chưa phù hợp chuyên môn", sort_order=1)
            db.add(reason); db.flush()

        def mk_app(job_id: int, st: str, internal_note: str | None = None) -> Application:
            a = Application(
                candidate_id=cand.id, job_id=job_id, cv_name_snapshot="cv.pdf",
                status=st, employer_notes=internal_note,
            )
            db.add(a); db.flush(); apps.append(a)
            return a

        a_sub = mk_app(ja.id, ApplicationStatus.SUBMITTED.value, "SECRET_INTERNAL_NOTE_DO_NOT_LEAK")
        a_rev = mk_app(ja.id, ApplicationStatus.REVIEWING.value)
        a_iv = mk_app(ja.id, ApplicationStatus.INTERVIEW.value)
        a_off = mk_app(ja.id, ApplicationStatus.OFFERED.value)
        a_wd = mk_app(ja.id, ApplicationStatus.WITHDRAWN.value)
        b_sub = mk_app(jb.id, ApplicationStatus.SUBMITTED.value)

        db.add(ApplicationNote(application_id=a_sub.id, author_id=emp_a.id, content="SECRET_PRIVATE_NOTE_TAB3"))
        iv_row = Interview(
            application_id=a_iv.id,
            scheduled_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2),
            duration_min=45, mode="Online", status="scheduled", created_by=emp_a.id,
        )
        db.add(iv_row)
        db.commit()

        yield {
            "db": db, "client": client, "reason": reason, "cand": cand,
            "ha": {"Authorization": f"Bearer {create_access_token(emp_a.id, 'employer')}"},
            "hb": {"Authorization": f"Bearer {create_access_token(emp_b.id, 'employer')}"},
            "hc": {"Authorization": f"Bearer {create_access_token(cand.id, 'candidate')}"},
            "a_sub": a_sub, "a_rev": a_rev, "a_iv": a_iv, "a_off": a_off, "a_wd": a_wd, "b_sub": b_sub,
            "iv_id": iv_row.id,
        }
    finally:
        for a in apps:
            db.query(Notification).filter(Notification.ref_id == a.id).delete()
            db.query(Interview).filter(Interview.application_id == a.id).delete()
            db.query(ApplicationNote).filter(ApplicationNote.application_id == a.id).delete()
            db.query(ApplicationStatusHistory).filter(ApplicationStatusHistory.application_id == a.id).delete()
            db.query(Application).filter(Application.id == a.id).delete()
        for j in jobs:
            db.query(Job).filter(Job.id == j.id).delete()
        for c in comps:
            db.query(Company).filter(Company.id == c.id).delete()
        for u in users:
            db.query(User).filter(User.id == u.id).delete()
        db.commit()
        db.close()


def test_reject_validation_and_permissions(rej_env):
    c, ha, hc = rej_env["client"], rej_env["ha"], rej_env["hc"]
    aid = rej_env["a_sub"].id
    assert c.post(f"/api/employer/applications/{aid}/reject", json={"reason_code": rej_env["reason"].slug}, headers=hc).status_code == 403
    assert c.post(f"/api/employer/applications/{rej_env['b_sub'].id}/reject", json={"reason_code": rej_env["reason"].slug}, headers=ha).status_code == 404
    assert c.post(f"/api/employer/applications/{aid}/reject", json={"reason_code": ""}, headers=ha).status_code == 422
    assert c.post(f"/api/employer/applications/{aid}/reject", json={"reason_code": "invalid_slug_xyz"}, headers=ha).status_code == 422
    assert c.post(f"/api/employer/applications/{aid}/reject", json={"reason_code": rej_env["reason"].slug, "message": "x" * 501}, headers=ha).status_code == 422
    assert c.post(f"/api/employer/applications/{rej_env['a_off'].id}/reject", json={"reason_code": rej_env["reason"].slug}, headers=ha).status_code == 409
    assert c.post(f"/api/employer/applications/{rej_env['a_wd'].id}/reject", json={"reason_code": rej_env["reason"].slug}, headers=ha).status_code == 409


def test_reject_idempotent_cancels_interview_and_no_internal_note_leak(rej_env):
    c, db, ha = rej_env["client"], rej_env["db"], rej_env["ha"]
    aid = rej_env["a_sub"].id
    msg = "<script>alert(1)</script> Cảm ơn bạn đã ứng tuyển."

    r1 = c.post(f"/api/employer/applications/{aid}/reject", json={"reason_code": rej_env["reason"].slug, "message": msg}, headers=ha)
    assert r1.status_code == 200 and r1.json()["already_rejected"] is False

    # Gọi lần 2 -> idempotent, không tạo thêm history/notification
    r2 = c.post(f"/api/employer/applications/{aid}/reject", json={"reason_code": rej_env["reason"].slug, "message": msg}, headers=ha)
    assert r2.status_code == 200 and r2.json()["already_rejected"] is True

    db.commit()
    hist_cnt = db.query(ApplicationStatusHistory).filter(ApplicationStatusHistory.application_id == aid).count()
    notif_rows = list(db.scalars(select(Notification).where(Notification.ref_id == aid)).all())
    assert hist_cnt == 1
    assert len(notif_rows) == 1
    notif_text = (notif_rows[0].message or "") + (notif_rows[0].payload_json or "")
    assert rej_env["reason"].name in notif_text
    assert "SECRET_INTERNAL_NOTE_DO_NOT_LEAK" not in notif_text
    assert "SECRET_PRIVATE_NOTE_TAB3" not in notif_text

    # Từ chối hồ sơ đang ở trạng thái INTERVIEW -> hủy lịch phỏng vấn đang hẹn
    r_iv = c.post(f"/api/employer/applications/{rej_env['a_iv'].id}/reject", json={"reason_code": rej_env["reason"].slug}, headers=ha)
    assert r_iv.status_code == 200 and r_iv.json()["cancelled_interviews"] == 1
    db.commit()
    iv_obj = db.get(Interview, rej_env["iv_id"])
    assert iv_obj.status == "cancelled"


def test_bulk_reject_partial_success(rej_env):
    c, ha = rej_env["client"], rej_env["ha"]
    ids = [rej_env["a_rev"].id, rej_env["a_off"].id, rej_env["b_sub"].id]
    res = c.post("/api/employer/applications/bulk-reject", json={"ids": ids, "reason_code": rej_env["reason"].slug}, headers=ha)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert data["rejected_count"] == 1
    assert data["skipped_count"] == 2
