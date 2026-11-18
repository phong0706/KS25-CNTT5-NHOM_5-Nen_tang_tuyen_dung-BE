"""Unit & API Integration tests cho luồng Xác minh công ty (Bước 2 -> Bước 8)."""
from datetime import date, timedelta
from pathlib import Path
import sys
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User
from app.services.company_verification_rules import (
    normalize_and_validate_mst,
    validate_license_file_bytes,
    validate_reason_text,
)

VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_mst_normalization_and_validation():
    assert normalize_and_validate_mst(" 010 124 8141 ") == "0101248141"
    assert normalize_and_validate_mst("0101-248-141") == "0101248141"
    assert normalize_and_validate_mst("0101248141 - 001") == "0101248141-001"
    assert normalize_and_validate_mst("0101248141001") == "0101248141-001"

    for bad in ["", "12345", "010124814A", "0101248141-12", "01012-48141001", "0101248141-0012"]:
        with pytest.raises(HTTPException) as exc:
            normalize_and_validate_mst(bad)
        assert exc.value.status_code == 422
        assert exc.value.detail["field"] == "mst"


def test_license_magic_bytes_rejects_exe_renamed_to_png():
    fake_png_exe = b"MZ\x90\x00\x03\x00\x00\x00fake-executable-bytes"
    with pytest.raises(HTTPException) as exc:
        validate_license_file_bytes(fake_png_exe)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "INVALID_LICENSE_FILE"

    assert validate_license_file_bytes(VALID_PNG_BYTES) == ("image/png", ".png")
    assert validate_license_file_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF") == ("image/jpeg", ".jpg")
    assert validate_license_file_bytes(b"%PDF-1.7\n1 0 obj") == ("application/pdf", ".pdf")


def test_reason_validation_requires_minimum_10_chars():
    for short in [None, "", "   ", "mờ quá", "123456789"]:
        with pytest.raises(HTTPException) as exc:
            validate_reason_text(short)
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "REASON_TOO_SHORT"
    assert validate_reason_text("  Ảnh giấy phép bị mờ không đọc được MST  ") == "Ảnh giấy phép bị mờ không đọc được MST"


def test_end_to_end_verification_workflow_and_concurrency():
    client = TestClient(app)
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    emp_a = User(email=f"emp_a_{tag}@test.vn", full_name="Employer A", password=hash_password("Pass123!"), role="employer", is_active=True)
    emp_b = User(email=f"emp_b_{tag}@test.vn", full_name="Employer B", password=hash_password("Pass123!"), role="employer", is_active=True)
    adm_1 = User(email=f"adm_1_{tag}@test.vn", full_name="Admin One", password=hash_password("Pass123!"), role="admin", is_active=True)
    adm_2 = User(email=f"adm_2_{tag}@test.vn", full_name="Admin Two", password=hash_password("Pass123!"), role="operator", is_active=True)
    db.add_all([emp_a, emp_b, adm_1, adm_2])
    db.commit()
    for u in (emp_a, emp_b, adm_1, adm_2):
        db.refresh(u)

    comp_a = Company(employer_id=emp_a.id, owner_id=emp_a.id, name=f"Công ty A {tag}", status=CompanyStatus.PENDING, verification_status="chua_xac_minh")
    comp_b = Company(employer_id=emp_b.id, owner_id=emp_b.id, name=f"Công ty B {tag}", status=CompanyStatus.PENDING, verification_status="chua_xac_minh")
    db.add_all([comp_a, comp_b])
    db.commit()
    db.refresh(comp_a)
    db.refresh(comp_b)

    h_emp_a = {"Authorization": f"Bearer {create_access_token(emp_a.id, emp_a.role)}"}
    h_emp_b = {"Authorization": f"Bearer {create_access_token(emp_b.id, emp_b.role)}"}
    h_adm_1 = {"Authorization": f"Bearer {create_access_token(adm_1.id, adm_1.role)}"}
    h_adm_2 = {"Authorization": f"Bearer {create_access_token(adm_2.id, adm_2.role)}"}

    try:
        # 1. Công ty chưa xác minh tạo tin với trạng thái đăng -> COMPANY_NOT_VERIFIED; tạo nháp -> 201
        job_body = {
            "title": "Backend Engineer Test", "level": "Middle", "work_type": "Toàn thời gian",
            "location": "Hà Nội", "quantity": 2, "deadline": (date.today() + timedelta(days=20)).isoformat(),
            "description": "Mô tả chi tiết vị trí tuyển dụng tối thiểu hai mươi ký tự.",
            "requirements": "Yêu cầu tối thiểu 10 ký tự.", "skills": ["Python"],
            "is_salary_negotiable": True, "benefits": [], "status": "pending",
        }
        r_pub = client.post("/api/employer/jobs", json=job_body, headers=h_emp_a)
        assert r_pub.status_code == 403
        assert r_pub.json()["detail"]["code"] == "COMPANY_NOT_VERIFIED"

        job_body["status"] = "draft"
        r_draft = client.post("/api/employer/jobs", json=job_body, headers=h_emp_a)
        assert r_draft.status_code == 201

        # 2. Gửi MST sai & gửi .exe đổi tên .png -> bị từ chối
        r_bad_mst = client.post(
            "/api/employer/company-verification",
            data={"mst": "12345-abc"},
            files={"file": ("license.png", VALID_PNG_BYTES, "image/png")},
            headers=h_emp_a,
        )
        assert r_bad_mst.status_code == 422 and r_bad_mst.json()["detail"]["field"] == "mst"

        r_bad_exe = client.post(
            "/api/employer/company-verification",
            data={"mst": "0101248141"},
            files={"file": ("giayphep.png", b"MZ\x90\x00\x03fake_exe", "image/png")},
            headers=h_emp_a,
        )
        assert r_bad_exe.status_code == 422 and r_bad_exe.json()["detail"]["code"] == "INVALID_LICENSE_FILE"

        # 3. Gửi hợp lệ lần 1 -> 201; gửi lần 2 khi đang chờ -> 409
        r_ok = client.post(
            "/api/employer/company-verification",
            data={"mst": "0101 248 141 - 001"},
            files={"file": ("giayphep.png", VALID_PNG_BYTES, "image/png")},
            headers=h_emp_a,
        )
        assert r_ok.status_code == 201
        verif_id = r_ok.json()["request"]["id"]
        assert r_ok.json()["request"]["mst"] == "0101248141-001"

        r_dup = client.post(
            "/api/employer/company-verification",
            data={"mst": "0101248141-001"},
            files={"file": ("giayphep.png", VALID_PNG_BYTES, "image/png")},
            headers=h_emp_a,
        )
        assert r_dup.status_code == 409

        # 4. Nhà tuyển dụng B không xem được yêu cầu & giấy phép của công ty A -> 403
        assert client.get(f"/api/employer/companies/{comp_a.id}/verification", headers=h_emp_b).status_code == 403
        assert client.get(f"/api/employer/company-verification/{verif_id}/license", headers=h_emp_b).status_code == 403

        # 5. Từ chối không lý do hoặc < 10 ký tự -> bị chặn (422)
        assert client.post(f"/api/admin/company-verifications/{verif_id}/reject", json={"reason": "", "version": 1}, headers=h_adm_1).status_code == 422
        assert client.post(f"/api/admin/company-verifications/{verif_id}/reject", json={"reason": "quá ngắn", "version": 1}, headers=h_adm_1).status_code == 422

        # 6. Hai admin cùng duyệt một yêu cầu với cùng version=1 -> 1 thành công (200), 1 nhận 409, chỉ 1 thông báo!
        r_a1 = client.post(f"/api/admin/company-verifications/{verif_id}/approve", json={"version": 1}, headers=h_adm_1)
        r_a2 = client.post(f"/api/admin/company-verifications/{verif_id}/approve", json={"version": 1}, headers=h_adm_2)
        assert sorted([r_a1.status_code, r_a2.status_code]) == [200, 409]

        db.rollback()
        notif_cnt = db.query(Notification).filter(Notification.user_id == emp_a.id, Notification.dedupe_key == f"company_verif:{verif_id}:da_xac_minh").count()
        assert notif_cnt == 1

        # 7. Khi đã xác minh -> đổi MST làm công ty về cho_duyet; duyệt lại rồi thu hồi -> tin chuyển sang reverify_pending, không xóa!
        open_job = Job(employer_id=emp_a.id, company_id=comp_a.id, title="Senior DevOps", status="published", deadline=date.today() + timedelta(days=15))
        db.add(open_job); db.commit(); db.refresh(open_job)

        r_mst_chg = client.put("/api/company/me", json={"name": comp_a.name, "tax_code": "0312345678"}, headers=h_emp_a)
        assert r_mst_chg.status_code == 200
        db.rollback()
        assert db.get(Company, comp_a.id).verification_status == "cho_duyet"
        assert db.get(Job, open_job.id).status == "reverify_pending"

        # Gửi và duyệt lại để test thu hồi xác minh
        r_resub = client.post("/api/employer/company-verification", data={"mst": "0312345678"}, files={"file": ("gp2.png", VALID_PNG_BYTES, "image/png")}, headers=h_emp_a)
        assert r_resub.status_code == 201
        assert client.post(f"/api/admin/company-verifications/{r_resub.json()['request']['id']}/approve", json={"version": 1}, headers=h_adm_1).status_code == 200
        db.rollback()
        assert db.get(Job, open_job.id).status == "published"

        r_rev = client.post(f"/api/admin/companies/{comp_a.id}/revoke-verification", json={"reason": "Giấy phép kinh doanh hết hiệu lực đối chiếu."}, headers=h_adm_1)
        assert r_rev.status_code == 200
        db.rollback()
        reloaded_job = db.get(Job, open_job.id)
        assert reloaded_job is not None and reloaded_job.status == "reverify_pending"

        # Thu hồi xong không cho tạo tin mới và không cho gia hạn deadline
        assert client.post("/api/employer/jobs", json=job_body, headers=h_emp_a).status_code == 403
        ext_body = {**job_body, "deadline": (date.today() + timedelta(days=45)).isoformat()}
        assert client.put(f"/api/employer/jobs/{open_job.id}", json=ext_body, headers=h_emp_a).status_code == 403
    finally:
        db.rollback()
        lic_dir = Path(__file__).resolve().parent.parent / "storage" / "company_licenses"
        for p in lic_dir.glob(f"lic_{comp_a.id}_*"):
            p.unlink(missing_ok=True)
        for u in (emp_a, emp_b, adm_1, adm_2):
            obj = db.get(User, u.id)
            if obj:
                db.delete(obj)
        db.commit()
        db.close()
