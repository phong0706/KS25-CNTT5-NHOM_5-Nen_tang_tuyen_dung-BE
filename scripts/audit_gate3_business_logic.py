"""Script kiểm toán Giai đoạn 3: Phân tích Logic nghiệp vụ, State Machines, Idempotence, Concurrency, Notifications, Audit logs.
Chạy trên môi trường app_db_test.
"""
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from fastapi.testclient import TestClient

os.environ["DB_NAME"] = "app_db_test"

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.job import Job
from app.models.company import Company
from app.models.company_verification import CompanyVerification
from app.models.company_logo import CompanyLogo
from app.models.application import Application, Interview, CV
from app.core.security import create_access_token
from app.services.job_moderation_rules import ALLOWED_TRANSITIONS, validate_job_transition, is_job_public
from app.services.pure_job_matching import compute_pure_match

client = TestClient(app)
db = SessionLocal()

def audit_gate3():
    report = {}

    # =========================================================================
    # 3.1 DUYỆT TIN TUYỂN DỤNG (JOB MODERATION)
    # =========================================================================
    emp = db.query(User).filter_by(role="employer", is_active=True).first()
    token_emp = create_access_token(emp.id, role="employer")
    
    # Tạo công ty chưa xác minh
    comp_unverif = db.query(Company).filter(Company.employer_id == emp.id).first()
    if comp_unverif:
        comp_unverif.verification_status = "chua_xac_minh"
        comp_unverif.is_verified = False
        comp_unverif.status = "pending"
        db.commit()
        
    # Tạo tin draft thuộc công ty này
    job_unverif = Job(
        title="Job Unverified Comp",
        employer_id=emp.id,
        company_id=comp_unverif.id if comp_unverif else 1,
        status="draft",
        work_type="Full-time",
        location="HN",
        salary_min=10,
        salary_max=20,
        is_salary_negotiable=0,
        views_count=0,
        quantity=1
    )
    db.add(job_unverif)
    db.commit()

    # Employer gửi duyệt tin
    r_submit = client.post(f"/api/employer/jobs/{job_unverif.id}/submit", headers={"Authorization": f"Bearer {token_emp}"})
    
    # Kiểm tra tin công khai: is_job_public logic
    pub_tests = [
        {"status": "published", "deadline": datetime.now(timezone.utc).date() + timedelta(days=5), "comp_verif": True, "deleted": False, "expect_public": True},
        {"status": "published", "deadline": datetime.now(timezone.utc).date() - timedelta(days=1), "comp_verif": True, "deleted": False, "expect_public": False},
        {"status": "published", "deadline": datetime.now(timezone.utc).date() + timedelta(days=5), "comp_verif": False, "deleted": False, "expect_public": False},
        {"status": "draft", "deadline": datetime.now(timezone.utc).date() + timedelta(days=5), "comp_verif": True, "deleted": False, "expect_public": False},
        {"status": "published", "deadline": datetime.now(timezone.utc).date() + timedelta(days=5), "comp_verif": True, "deleted": True, "expect_public": False},
    ]
    pub_results = []
    for pt in pub_tests:
        today = datetime.now(timezone.utc).date()
        del_at = datetime.now() if pt.get("deleted") else None
        res = is_job_public(pt["status"], pt["deadline"], pt["comp_verif"], today, del_at)
        pub_results.append({**pt, "deadline": str(pt["deadline"]), "actual_public": res, "passed": (res == pt["expect_public"])})

    report["3.1_job_moderation"] = {
        "transition_matrix": ALLOWED_TRANSITIONS,
        "unverified_company_submit_status": r_submit.status_code,
        "unverified_company_submit_response": r_submit.json() if r_submit.status_code in (200, 400, 403, 409, 422) else r_submit.text[:120],
        "blocked_at_backend": r_submit.status_code in (400, 403, 409, 422),
        "is_job_public_rules_check": pub_results
    }

    # =========================================================================
    # 3.2 XÁC MINH CÔNG TY (COMPANY VERIFICATION)
    # =========================================================================
    # Kiểm tra endpoint duyệt thủ công và cập nhật MST
    admin = db.query(User).filter_by(role="admin", is_active=True).first()
    token_admin = create_access_token(admin.id, role="admin")
    
    # Admin duyệt không lý do
    r_verif_no_reason = client.post("/api/admin/verifications/1/approve", json={"reason": ""}, headers={"Authorization": f"Bearer {token_admin}"})
    
    report["3.2_company_verification"] = {
        "verif_states": ["chua_xac_minh", "cho_duyet", "da_xac_minh", "tu_choi", "thu_hoi"],
        "admin_approve_endpoint_status": r_verif_no_reason.status_code,
    }

    # =========================================================================
    # 3.3 LOGO CÔNG TY (COMPANY LOGO LIFECYCLE)
    # =========================================================================
    # Kiểm tra xem từ chối logo có bắt buộc lý do không
    r_logo_reject_no_reason = client.post("/api/admin/logos/1/reject", json={"reason": ""}, headers={"Authorization": f"Bearer {token_admin}"})
    
    report["3.3_company_logo"] = {
        "reject_no_reason_status": r_logo_reject_no_reason.status_code,
        "reject_no_reason_blocked": r_logo_reject_no_reason.status_code in (400, 422)
    }

    # =========================================================================
    # 3.5 VIỆC LÀM PHÙ HỢP (MATCHING LOGIC - 10 BỘ DỮ LIỆU)
    # =========================================================================
    matching_tests = []
    cases = [
        # (c_skills, c_level, c_loc, c_sal, j_skills, j_level, j_loc, j_sal_min, j_sal_max)
        (["Python", "FastAPI", "Docker"], "Senior", "Hà Nội", 30000000, ["Python", "FastAPI", "Docker"], "Senior", "Hà Nội", 25000000, 35000000),
        (["React", "TypeScript", "TailwindCSS"], "Junior", "Hồ Chí Minh", 12000000, ["React", "JavaScript", "HTML/CSS"], "Junior", "Hồ Chí Minh", 10000000, 15000000),
        (["Java", "Spring Boot", "MySQL"], "Middle", "Đà Nẵng", 20000000, ["Java", "Spring Boot", "MySQL"], "Middle", "Đà Nẵng", 18000000, 25000000),
        (["Docker", "Kubernetes", "AWS"], "Senior", "Hà Nội", 40000000, ["Docker", "Kubernetes", "CI/CD"], "Senior", "Hà Nội", 35000000, 45000000),
        (["Python", "PyTorch", "Pandas"], "Middle", "Hồ Chí Minh", 25000000, ["Python", "Machine Learning", "NLP"], "Middle", "Hồ Chí Minh", 22000000, 30000000),
        (["Flutter", "Dart", "Firebase"], "Junior", "Hà Nội", 15000000, ["Flutter", "Dart", "REST API"], "Junior", "Hà Nội", 12000000, 18000000),
        (["Node.js", "Express", "MongoDB"], "Middle", "Hồ Chí Minh", 22000000, ["Node.js", "TypeScript", "PostgreSQL"], "Middle", "Hồ Chí Minh", 20000000, 28000000),
        (["PHP", "Laravel", "MySQL"], "Middle", "Đà Nẵng", 18000000, ["PHP", "Laravel", "Vue.js"], "Middle", "Đà Nẵng", 16000000, 22000000),
        (["Golang", "gRPC", "Docker"], "Senior", "Hà Nội", 35000000, ["Golang", "Kubernetes", "Redis"], "Senior", "Hà Nội", 30000000, 40000000),
        (["Selenium", "Postman", "SQL"], "Junior", "Hồ Chí Minh", 12000000, ["Selenium", "Automation", "Jira"], "Junior", "Hồ Chí Minh", 10000000, 15000000),
    ]

    for idx, (c_sk, c_lvl, c_loc, c_sal, j_sk, j_lvl, j_loc, j_min, j_max) in enumerate(cases, 1):
        res = compute_pure_match(
            job_skills=j_sk,
            job_level=j_lvl,
            job_location=j_loc,
            job_salary_min=j_min,
            job_salary_max=j_max,
            job_is_negotiable=False,
            cand_skills=c_sk,
            cand_level=c_lvl,
            cand_location=c_loc,
            cand_open_to_relocate=False,
            cand_expected_salary=c_sal
        )
        total_score = res["total_score"] if res else 0.0
        matching_tests.append({
            "case": idx,
            "candidate_skills": c_sk,
            "job_skills": j_sk,
            "total_score": total_score,
            "in_range_0_1": (0.0 <= total_score <= 1.0),
            "breakdown": res
        })

    report["3.5_matching_logic"] = {
        "ten_sample_calculations": matching_tests,
        "all_scores_valid": all(t["in_range_0_1"] for t in matching_tests)
    }

    # =========================================================================
    # 3.6 ĐƠN ỨNG TUYỂN & LỊCH PHỎNG VẤN (INTERVIEWS)
    # =========================================================================
    past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    r_past_interview = client.post(
        "/api/employer/interviews",
        json={"application_id": 1, "scheduled_at": past_date, "location": "Online"},
        headers={"Authorization": f"Bearer {token_emp}"}
    )
    report["3.6_interviews"] = {
        "schedule_past_date_status": r_past_interview.status_code,
        "schedule_past_date_response": r_past_interview.text[:120]
    }

    # =========================================================================
    # 3.8 SỐ ĐẾM BỘ LỌC (FACETS PARITY)
    # =========================================================================
    r_jobs = client.get("/api/jobs?page=1&page_size=5")
    if r_jobs.status_code == 200:
        jd = r_jobs.json()
        report["3.8_filter_counts"] = {
            "api_total": jd.get("total"),
            "facets_total_jobs": jd.get("facets", {}).get("total_jobs"),
            "facets_locations_count": len(jd.get("facets", {}).get("locations", [])),
            "facets_levels_count": len(jd.get("facets", {}).get("levels", [])),
        }
    else:
        report["3.8_filter_counts"] = {"status": r_jobs.status_code}

    with open("audit_gate3_business_logic.json", "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, default=str)

    print("Gate 3 audit finished successfully.")

if __name__ == "__main__":
    audit_gate3()
