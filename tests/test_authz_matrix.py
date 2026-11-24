"""Test ma trận phân quyền toàn hệ thống (5 danh tính) & IDOR trên DB test."""
from pathlib import Path
import uuid
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, SavedSearch
from app.models.candidate import CandidateProfile
from app.models.company import Company, CompanyStatus
from app.models.cv_document import CVDocument
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User
from tests.authz_matrix_helper import (
    PUBLIC_WHITELIST,
    ensure_raw_test_tables,
    extract_route_roles,
    materialize_path,
    write_authz_matrix_doc,
)

client = TestClient(app)
client_matrix = TestClient(app, raise_server_exceptions=False)


def _mk_user(db, role: str, is_active: bool = True) -> User:
    u = User(
        email=f"authz_{role}_{uuid.uuid4().hex[:8]}@test.vn",
        password=hash_password("TestPass123!"),
        full_name=f"Authz {role}",
        role=role,
        is_active=is_active,
        token_version=1,
    )
    db.add(u)
    db.flush()
    return u


def _hdr(u: User | None) -> dict[str, str]:
    if not u:
        return {}
    tok = create_access_token(u.id, u.role, u.token_version)
    return {"Authorization": f"Bearer {tok}"}


def test_authz_matrix_all_routes_and_generate_doc():
    db = SessionLocal()
    ensure_raw_test_tables(db)
    created_ids: list[int] = []
    try:
        cand = _mk_user(db, "candidate", True)
        emp = _mk_user(db, "employer", True)
        adm = _mk_user(db, "admin", True)
        locked = _mk_user(db, "candidate", False)
        created_ids.extend([cand.id, emp.id, adm.id, locked.id])
        db.commit()

        identities = [
            ("guest", None, None),
            ("candidate", "candidate", _hdr(cand)),
            ("employer", "employer", _hdr(emp)),
            ("admin", "admin", _hdr(adm)),
            ("locked", "locked", _hdr(locked)),
        ]

        doc_rows: list[tuple[str, str, bool, str, str]] = []
        routes = [r for r in app.routes if isinstance(r, APIRoute)]
        routes.sort(key=lambda r: (r.path, sorted(r.methods)[0] if r.methods else ""))

        for r in routes:
            for method in sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS")):
                allowed_roles = extract_route_roles(r)
                if allowed_roles is None:
                    assert (method, r.path) in PUBLIC_WHITELIST, (
                        f"Route không kiểm tra vai trò ngoài whitelist: {method} {r.path}"
                    )

                url = materialize_path(r.path)
                statuses = {}
                for idx, (name, role_val, headers) in enumerate(identities):
                    resp = client_matrix.request(method, url, headers=headers or {}, json={})
                    if r.path == "/api/auth/logout" and name in ("candidate", "employer", "admin"):
                        u_obj = {"candidate": cand, "employer": emp, "admin": adm}[name]
                        db.commit()
                        db.refresh(u_obj)
                        identities[idx] = (name, role_val, _hdr(u_obj))
                    statuses[name] = resp.status_code

                    if allowed_roles is None:
                        assert resp.status_code not in (401, 403), (
                            f"Public route {method} {r.path} returned {resp.status_code} for {name}"
                        )
                    else:
                        if name == "guest":
                            assert resp.status_code == 401, f"Guest {method} {r.path} got {resp.status_code}"
                        elif name == "locked":
                            assert resp.status_code in (401, 403), f"Locked {method} {r.path} got {resp.status_code}"
                        elif role_val not in allowed_roles:
                            assert resp.status_code == 403, (
                                f"Role {role_val} on {method} {r.path} (allowed={allowed_roles}) got {resp.status_code}"
                            )
                        else:
                            assert resp.status_code not in (401, 403), (
                                f"Allowed role {role_val} on {method} {r.path} got {resp.status_code}"
                            )

                is_pub = allowed_roles is None
                roles_str = "Công khai" if is_pub else ", ".join(sorted(allowed_roles))
                res_str = ", ".join(f"{k}:{v}" for k, v in statuses.items())
                doc_rows.append((method, r.path, is_pub, roles_str, res_str))

        doc_path = Path(__file__).resolve().parents[2] / "docs" / "authz-matrix.md"
        write_authz_matrix_doc(doc_rows, doc_path)
    finally:
        for uid in created_ids:
            u = db.get(User, uid)
            if u:
                db.delete(u)
        db.commit()
        db.close()


def test_idor_isolation_between_users():
    """IDOR: candidate A/B và employer A/B không đọc/sửa/xóa được đối tượng của nhau (404)."""
    db = SessionLocal()
    cleanup = []
    try:
        cand_a, cand_b = _mk_user(db, "candidate"), _mk_user(db, "candidate")
        emp_a, emp_b = _mk_user(db, "employer"), _mk_user(db, "employer")
        cleanup.extend([cand_a.id, cand_b.id, emp_a.id, emp_b.id])

        prof_b = CandidateProfile(user_id=cand_b.id, is_public=False)
        cv_b = CVDocument(user_id=cand_b.id, title="CV B", template_slug="simple", content_json="{}")
        ss_b = SavedSearch(user_id=cand_b.id, name="Search B", filters_json="{}")
        notif_b = Notification(user_id=cand_b.id, type="SYSTEM", title="N", message="M", is_read=False)
        comp_a = Company(employer_id=emp_a.id, name=f"Comp A {uuid.uuid4().hex[:6]}", status=CompanyStatus.VERIFIED, verification_status="da_xac_minh")
        comp_b = Company(employer_id=emp_b.id, name=f"Comp B {uuid.uuid4().hex[:6]}", status=CompanyStatus.VERIFIED, verification_status="da_xac_minh")
        db.add_all([prof_b, cv_b, ss_b, notif_b, comp_a, comp_b])
        db.flush()

        has_cl_tbl = inspect(db.bind).has_table("candidate_cover_letters")
        cl_b_id = None
        if has_cl_tbl:
            db.execute(text("INSERT INTO candidate_cover_letters (candidate_id, title, content) VALUES (:cid, 'CL B', 'Body')"), {"cid": cand_b.id})
            cl_b_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        job_b = Job(title="Job B", company_id=comp_b.id, employer_id=emp_b.id, status="OPEN")
        db.add(job_b)
        db.flush()

        app_b = Application(job_id=job_b.id, candidate_id=cand_b.id, candidate_profile_id=prof_b.id, status="pending", active_flag=1)
        db.add(app_b)
        db.commit()

        ha, hea = _hdr(cand_a), _hdr(emp_a)

        # Candidate A truy cập đối tượng của Candidate B -> 404
        assert client.get(f"/api/candidate/cv-documents/{cv_b.id}", headers=ha).status_code == 404
        assert client.delete(f"/api/candidate/cv-documents/{cv_b.id}", headers=ha).status_code == 404
        if cl_b_id is not None:
            assert client.delete(f"/api/candidate/cover-letters/{cl_b_id}", headers=ha).status_code == 404
        assert client.delete(f"/api/candidate/saved-searches/{ss_b.id}", headers=ha).status_code == 404
        assert client.post(f"/api/notifications/{notif_b.id}/read", headers=ha).status_code == 404
        assert client.get(f"/api/profiles/{prof_b.id}", headers=ha).status_code == 404
        assert client.put(f"/api/profiles/{prof_b.id}", headers=ha, json={"headline": "hack"}).status_code == 404
        assert client.get(f"/api/applications/{app_b.id}", headers=ha).status_code == 404

        # Employer A truy cập đối tượng của Employer B -> 404
        assert client.get(f"/api/employer/jobs/{job_b.id}", headers=hea).status_code == 404
        assert client.delete(f"/api/employer/jobs/{job_b.id}", headers=hea).status_code == 404
        assert client.get(f"/api/employer/applications/{app_b.id}", headers=hea).status_code == 404
        assert client.post(f"/api/employer/applications/{app_b.id}/reject", headers=hea, json={"reason_code": "other"}).status_code == 404
        assert client.get(f"/api/companies/{comp_b.id}/logos", headers=hea).status_code == 404
        assert client.get(f"/api/applications/{app_b.id}", headers=hea).status_code == 404
    finally:
        db.rollback()
        insp = inspect(db.bind)
        for tbl, col in [
            ("applications", "candidate_id"), ("jobs", "employer_id"),
            ("companies", "employer_id"), ("notifications", "user_id"),
            ("saved_searches", "user_id"), ("candidate_cover_letters", "candidate_id"),
            ("cv_documents", "user_id"), ("candidate_profiles", "user_id"),
        ]:
            if cleanup and insp.has_table(tbl):
                db.execute(text(f"DELETE FROM {tbl} WHERE {col} IN :ids"), {"ids": tuple(cleanup)})
        for uid in cleanup:
            u = db.get(User, uid)
            if u:
                db.delete(u)
        db.commit()
        db.close()
