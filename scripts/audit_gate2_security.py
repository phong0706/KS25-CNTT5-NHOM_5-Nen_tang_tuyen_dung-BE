"""Kiểm toán Giai đoạn 2: Toàn diện Bảo mật (Authentication, RBAC, IDOR, Escalation, Injection, Files, PII, Git History).
Chạy trên môi trường app_db_test qua TestClient (FastAPI).
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi.testclient import TestClient

# Đảm bảo môi trường chạy trên app_db_test
os.environ["DB_NAME"] = "app_db_test"

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.user import User
from app.models.job import Job
from app.models.company import Company
from app.models.application import Application, CV

client = TestClient(app)
db = SessionLocal()

def get_or_create_test_users():
    # 1. Admin
    admin = db.query(User).filter_by(role="admin", is_active=True).first()
    # 2. Candidate A
    cand_a = db.query(User).filter_by(role="candidate", is_active=True).first()
    # 3. Candidate B
    cand_b = db.query(User).filter(User.role == "candidate", User.is_active == True, User.id != cand_a.id).first()
    # 4. Employer A
    emp_a = db.query(User).filter_by(role="employer", is_active=True).first()
    # 5. Employer B
    emp_b = db.query(User).filter(User.role == "employer", User.is_active == True, User.id != emp_a.id).first()

    tokens = {
        "admin": create_access_token(admin.id, role="admin") if admin else None,
        "cand_a": create_access_token(cand_a.id, role="candidate") if cand_a else None,
        "cand_b": create_access_token(cand_b.id, role="candidate") if cand_b else None,
        "emp_a": create_access_token(emp_a.id, role="employer") if emp_a else None,
        "emp_b": create_access_token(emp_b.id, role="employer") if emp_b else None,
        "users": {
            "admin": admin.id if admin else None,
            "cand_a": cand_a.id if cand_a else None,
            "cand_b": cand_b.id if cand_b else None,
            "emp_a": emp_a.id if emp_a else None,
            "emp_b": emp_b.id if emp_b else None,
        }
    }
    return tokens

def audit_phase2():
    tokens = get_or_create_test_users()
    cand_a_token = tokens["cand_a"]
    cand_b_token = tokens["cand_b"]
    emp_a_token = tokens["emp_a"]
    emp_b_token = tokens["emp_b"]
    admin_token = tokens["admin"]
    users = tokens["users"]

    results = {}

    # =========================================================================
    # 2.1 XÁC THỰC (AUTHENTICATION)
    # =========================================================================
    auth_tests = {}
    
    # a) Expired token
    expired_payload = {
        "sub": str(users["cand_a"]),
        "role": "candidate",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "token_ver": 1
    }
    exp_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm="HS256")
    r_exp = client.get("/api/candidate/profile", headers={"Authorization": f"Bearer {exp_token}"})
    auth_tests["expired_token_status"] = r_exp.status_code
    auth_tests["expired_token_pass"] = (r_exp.status_code == 401)

    # b) Tampered token
    tampered_token = cand_a_token[:-5] + "AAAAA"
    r_tamp = client.get("/api/candidate/profile", headers={"Authorization": f"Bearer {tampered_token}"})
    auth_tests["tampered_token_status"] = r_tamp.status_code
    auth_tests["tampered_token_pass"] = (r_tamp.status_code == 401)

    # c) Algorithm "none" attack
    none_payload = {"sub": str(users["admin"]), "role": "admin"}
    # Construct unverified token with none algorithm
    try:
        import base64
        h_b64 = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(none_payload).encode()).decode().rstrip("=")
        none_token = f"{h_b64}.{p_b64}."
        r_none = client.get("/api/admin/jobs", headers={"Authorization": f"Bearer {none_token}"})
        auth_tests["algorithm_none_status"] = r_none.status_code
        auth_tests["algorithm_none_rejected"] = (r_none.status_code == 401)
    except Exception as e:
        auth_tests["algorithm_none_error"] = str(e)

    # d) Passwordless login check
    r_pwdless = client.post("/api/auth/login", json={"email": "admin@example.com", "password": ""})
    auth_tests["passwordless_status"] = r_pwdless.status_code
    auth_tests["passwordless_blocked"] = (r_pwdless.status_code in (400, 401, 422))

    # e) Token version / session revocation on password change
    # Check if user has token_version in db and if it is verified on auth
    u = db.get(User, users["cand_a"])
    has_token_ver = hasattr(u, "token_version") or hasattr(u, "token_ver")
    auth_tests["user_model_has_token_version"] = has_token_ver

    results["2.1_authentication"] = auth_tests

    # =========================================================================
    # 2.2 PHÂN QUYỀN (RBAC MATRIX)
    # =========================================================================
    endpoints_to_test = [
        # (method, path, body, expected_status_by_role: {guest, candidate, employer, admin})
        ("GET", "/api/admin/audit-logs", None, {"guest": 401, "candidate": 403, "employer": 403, "admin": 200}),
        ("GET", "/api/admin/companies", None, {"guest": 401, "candidate": 403, "employer": 403, "admin": 200}),
        ("GET", "/api/admin/verifications", None, {"guest": 401, "candidate": 403, "employer": 403, "admin": 200}),
        ("GET", "/api/employer/jobs", None, {"guest": 401, "candidate": 403, "employer": 200, "admin": 403}),
        ("GET", "/api/employer/applications", None, {"guest": 401, "candidate": 403, "employer": 200, "admin": 403}),
        ("GET", "/api/candidate/applications", None, {"guest": 401, "candidate": 200, "employer": 403, "admin": 403}),
        ("GET", "/api/candidate/cvs", None, {"guest": 401, "candidate": 200, "employer": 403, "admin": 403}),
        ("GET", "/api/jobs", None, {"guest": 200, "candidate": 200, "employer": 200, "admin": 200}),
        ("GET", "/api/companies", None, {"guest": 200, "candidate": 200, "employer": 200, "admin": 200}),
    ]

    rbac_matrix = []
    role_tokens = {
        "guest": None,
        "candidate": cand_a_token,
        "employer": emp_a_token,
        "admin": admin_token,
    }

    for method, path, body, expected in endpoints_to_test:
        row = {"method": method, "path": path, "roles": {}}
        for role, token in role_tokens.items():
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            if method == "GET":
                r = client.get(path, headers=headers)
            elif method == "POST":
                r = client.post(path, json=body, headers=headers)
            
            exp_code = expected[role]
            actual_code = r.status_code
            matches = (actual_code == exp_code)
            # Some admin endpoints allow 200 for employer/candidate if shared or 403
            row["roles"][role] = {
                "expected": exp_code,
                "actual": actual_code,
                "passed": matches
            }
        rbac_matrix.append(row)

    results["2.2_rbac_matrix"] = rbac_matrix

    # =========================================================================
    # 2.3 IDOR (INSECURE DIRECT OBJECT REFERENCE)
    # =========================================================================
    idor_tests = {}
    
    # a) Candidate A accessing Candidate B's CV
    cv_b = db.query(CV).filter_by(candidate_id=users["cand_b"]).first()
    if cv_b:
        # Candidate A tries to GET /api/candidate/cvs/{id} or /file
        r_idor_cv = client.get(f"/api/candidate/cvs/{cv_b.id}/file", headers={"Authorization": f"Bearer {cand_a_token}"})
        r_idor_cv_del = client.delete(f"/api/candidate/cvs/{cv_b.id}", headers={"Authorization": f"Bearer {cand_a_token}"})
        idor_tests["candidate_cross_cv_get_status"] = r_idor_cv.status_code
        idor_tests["candidate_cross_cv_del_status"] = r_idor_cv_del.status_code
        idor_tests["cv_idor_protected"] = r_idor_cv.status_code in (403, 404) and r_idor_cv_del.status_code in (403, 404)
    else:
        idor_tests["candidate_cross_cv"] = "No CV found for Candidate B"

    # b) Candidate A viewing Candidate B's Application
    app_b = db.query(Application).filter_by(candidate_id=users["cand_b"]).first()
    if app_b:
        r_idor_app = client.get(f"/api/candidate/applications/{app_b.id}", headers={"Authorization": f"Bearer {cand_a_token}"})
        idor_tests["candidate_cross_app_get_status"] = r_idor_app.status_code
        idor_tests["app_idor_protected"] = r_idor_app.status_code in (403, 404)
    else:
        idor_tests["candidate_cross_app"] = "No application found for Candidate B"

    # c) Employer A modifying Employer B's Job
    job_b = db.query(Job).filter_by(employer_id=users["emp_b"]).first()
    if job_b:
        r_idor_job = client.put(f"/api/employer/jobs/{job_b.id}", json={"title": "Hacked Title"}, headers={"Authorization": f"Bearer {emp_a_token}"})
        idor_tests["employer_cross_job_put_status"] = r_idor_job.status_code
        idor_tests["job_idor_protected"] = r_idor_job.status_code in (403, 404)
    else:
        idor_tests["employer_cross_job"] = "No job found for Employer B"

    results["2.3_idor"] = idor_tests

    # =========================================================================
    # 2.4 LEO QUYỀN (PRIVILEGE ESCALATION)
    # =========================================================================
    escalation_tests = {}
    
    # a) Candidate tries to change role to admin via profile update
    r_esc_role = client.put("/api/candidate/profile", json={"role": "admin", "full_name": "Attacker"}, headers={"Authorization": f"Bearer {cand_a_token}"})
    u_after = db.get(User, users["cand_a"])
    escalation_tests["role_tamper_attempt_status"] = r_esc_role.status_code
    escalation_tests["role_after_tamper"] = u_after.role
    escalation_tests["role_tamper_blocked"] = (u_after.role == "candidate")

    # b) Employer tries to approve own job via admin endpoint
    if job_b:
        r_esc_approve = client.patch(f"/api/admin/jobs/{job_b.id}/approve", headers={"Authorization": f"Bearer {emp_b_token}"})
        escalation_tests["employer_self_approve_status"] = r_esc_approve.status_code
        escalation_tests["employer_self_approve_blocked"] = r_esc_approve.status_code in (401, 403)

    results["2.4_privilege_escalation"] = escalation_tests

    # =========================================================================
    # 2.5 TIÊM (SQL & XSS INJECTION)
    # =========================================================================
    injection_tests = {}
    
    # a) SQL Injection in search parameters
    sqli_payloads = [
        "' OR '1'='1",
        "1; DROP TABLE fake_test_table--",
        "test' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20-- "
    ]
    sqli_results = []
    for payload in sqli_payloads:
        r_q = client.get("/api/jobs", params={"q": payload})
        r_sort = client.get("/api/jobs", params={"sort": payload})
        r_loc = client.get("/api/jobs", params={"location": payload})
        sqli_results.append({
            "payload": payload,
            "q_status": r_q.status_code,
            "sort_status": r_sort.status_code,
            "loc_status": r_loc.status_code,
            "safe": r_q.status_code in (200, 422) and r_sort.status_code in (200, 422) and r_loc.status_code in (200, 422)
        })
    injection_tests["sqli_results"] = sqli_results

    # b) XSS Payload in job rejection reason or text field
    xss_payload = "<script>alert('XSS')</script><img src=x onerror=alert(1)>"
    # Test if API accepts without crash and check frontend escaping
    injection_tests["xss_verbatim_storage_required"] = True

    results["2.5_injections"] = injection_tests

    # =========================================================================
    # 2.6 TẢI FILE & TRUY CẬP TRỰC TIẾP TÀI LIỆU (CV & LOGO)
    # =========================================================================
    file_tests = {}
    
    # a) Upload fake PDF (executable file with .pdf extension)
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This is an executable binary"
    files = {"file": ("malicious.pdf", fake_pdf, "application/pdf")}
    r_up_fake = client.post("/api/candidate/cvs", files=files, headers={"Authorization": f"Bearer {cand_a_token}"})
    file_tests["fake_pdf_mz_status"] = r_up_fake.status_code
    file_tests["fake_pdf_mz_blocked"] = (r_up_fake.status_code in (400, 415, 422))

    # b) SVG upload with embedded script as logo
    svg_payload = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    files_svg = {"file": ("evil.svg", svg_payload, "image/svg+xml")}
    r_up_svg = client.post("/api/company/me/logo", files=files_svg, headers={"Authorization": f"Bearer {emp_a_token}"})
    file_tests["svg_upload_status"] = r_up_svg.status_code
    file_tests["svg_upload_blocked"] = (r_up_svg.status_code in (400, 415, 422))

    # c) Path traversal in filename
    files_trav = {"file": ("../../../../etc/passwd.pdf", b"%PDF-1.4\nvalid mock pdf content", "application/pdf")}
    r_trav = client.post("/api/candidate/cvs", files=files_trav, headers={"Authorization": f"Bearer {cand_a_token}"})
    file_tests["path_traversal_status"] = r_trav.status_code

    # d) Public static access to CV files without auth
    # Check if /uploads/cvs or /static/cvs is exposed
    r_static_cv = client.get("/uploads/cvs/some_file.pdf")
    file_tests["static_cv_direct_access_status"] = r_static_cv.status_code
    file_tests["static_cv_forbidden_or_404"] = (r_static_cv.status_code in (403, 404))

    results["2.6_file_upload_security"] = file_tests

    # =========================================================================
    # 2.7 LỘ DỮ LIỆU & PII
    # =========================================================================
    pii_tests = {}
    
    # a) Public jobs response PII
    r_pub_jobs = client.get("/api/jobs?page_size=5")
    jobs_json = r_pub_jobs.text
    pii_tests["jobs_leaks_password_hash"] = "$2b$" in jobs_json or "$2a$" in jobs_json
    pii_tests["jobs_leaks_email"] = "@gmail.com" in jobs_json or "@test.com" in jobs_json
    
    # b) Public company response PII
    r_pub_comp = client.get("/api/companies?page_size=5")
    comp_json = r_pub_comp.text
    pii_tests["comp_leaks_password_hash"] = "$2b$" in comp_json or "$2a$" in comp_json
    
    # c) Traceback leak in 500
    r_404 = client.get("/api/non-existent-endpoint-xyz")
    pii_tests["error_leaks_traceback"] = "Traceback (most recent call last)" in r_404.text

    results["2.7_data_exposure"] = pii_tests

    # =========================================================================
    # 2.9 CẤU HÌNH BẢO MẬT & CORS (C12)
    # =========================================================================
    config_tests = {}
    
    # CORS Origins
    cors_str = os.getenv("CORS_ORIGINS", "")
    config_tests["cors_configured"] = cors_str
    config_tests["cors_has_5501"] = "5501" in cors_str
    config_tests["cors_has_5502"] = "5502" in cors_str
    config_tests["cors_has_wildcard"] = "*" in cors_str
    config_tests["cors_safe"] = not ("*" in cors_str)

    # Git tracking of .env
    p_git = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True)
    config_tests["env_tracked_by_git"] = bool(p_git.stdout.strip())

    results["2.9_config_and_cors"] = config_tests

    # =========================================================================
    # 2.10 QUÉT BÍ MẬT TRONG LỊCH SỬ GIT
    # =========================================================================
    git_tests = {}
    cmd_git_log = "git log -p -S JWT_SECRET -n 5"
    p_log = subprocess.run(cmd_git_log, shell=True, capture_output=True, text=True)
    git_tests["git_history_jwt_secret_scan_exit"] = p_log.returncode
    git_tests["git_history_has_jwt_secret_commits"] = "JWT_SECRET=" in p_log.stdout

    results["2.10_git_history"] = git_tests

    with open("audit_gate2_security.json", "w", encoding="utf-8") as out:
        json.dump(results, out, indent=2, default=str)

    print("Security audit completed. Saved audit_gate2_security.json")

if __name__ == "__main__":
    audit_phase2()
