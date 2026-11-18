"""Kiểm thử đồng thời (concurrency) và tính idempotent của luồng duyệt tin (Lớp D).

Sử dụng 2 session/kết nối DB riêng biệt song song, không dùng sleep để chờ.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
import sys
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.job_status_history import JobStatusHistory
from app.models.notification import Notification
from app.models.user import User
from app.services.job_moderation_service import (
    approve_job_service,
    withdraw_job_to_draft_service,
)


def setup_concurrent_fixture():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:8]
        emp = User(
            email=f"emp_{tag}@test.com",
            password=hash_password("Pass123@"),
            full_name=f"Emp {tag}",
            role="employer",
            is_active=True,
        )
        admin1 = User(
            email=f"admin1_{tag}@test.com",
            password=hash_password("Pass123@"),
            full_name=f"Admin1 {tag}",
            role="admin",
            is_active=True,
        )
        admin2 = User(
            email=f"admin2_{tag}@test.com",
            password=hash_password("Pass123@"),
            full_name=f"Admin2 {tag}",
            role="admin",
            is_active=True,
        )
        db.add_all([emp, admin1, admin2])
        db.flush()

        comp = Company(
            employer_id=emp.id,
            name=f"Company {tag}",
            tax_code=f"010{tag[:7]}",
            address="Hà Nội",
            verification_status="da_xac_minh",
            status=CompanyStatus.VERIFIED,
            is_verified=True,
        )
        db.add(comp)
        db.flush()

        job = Job(
            employer_id=emp.id,
            company_id=comp.id,
            title=f"DevOps Engineer {tag}",
            status="pending",
            version=1,
            deadline=date.today() + timedelta(days=20),
        )
        db.add(job)
        db.commit()
        return emp.id, admin1.id, admin2.id, job.id
    finally:
        db.close()


def test_concurrency_two_admins_approve_same_job():
    """Hai admin cùng duyệt 1 tin với version=1: đúng 1 thành công (200), 1 nhận 409."""
    emp_id, admin1_id, admin2_id, job_id = setup_concurrent_fixture()

    def do_approve(admin_id):
        db = SessionLocal()
        try:
            return approve_job_service(
                db=db,
                job_id=job_id,
                admin_id=admin_id,
                expected_version=1,
            )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(do_approve, admin1_id)
        f2 = executor.submit(do_approve, admin2_id)
        results = []
        errors = []
        for f in (f1, f2):
            try:
                results.append(f.result())
            except HTTPException as e:
                errors.append(e)

    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0].status_code == 409
    assert errors[0].detail in ("VERSION_CONFLICT", "INVALID_TRANSITION")

    # Kiểm tra DB chỉ có đúng 1 dòng lịch sử và 1 thông báo
    check_db = SessionLocal()
    try:
        final_job = check_db.get(Job, job_id)
        assert final_job.status == "published"
        assert final_job.version == 2

        histories = check_db.query(JobStatusHistory).filter_by(job_id=job_id).all()
        assert len(histories) == 1

        notifs = check_db.query(Notification).filter_by(user_id=emp_id).all()
        assert len(notifs) == 1
    finally:
        check_db.close()


def test_concurrency_approve_and_withdraw():
    """Admin duyệt và Employer rút về nháp cùng lúc: 1 thành công, 1 xung đột, trạng thái cuối nhất quán."""
    emp_id, admin1_id, _, job_id = setup_concurrent_fixture()

    def do_admin():
        db = SessionLocal()
        try:
            return approve_job_service(db, job_id, admin1_id, expected_version=1)
        finally:
            db.close()

    def do_employer():
        db = SessionLocal()
        try:
            return withdraw_job_to_draft_service(db, job_id, emp_id, expected_version=1)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(do_admin)
        f2 = executor.submit(do_employer)
        results = []
        errors = []
        for f in (f1, f2):
            try:
                results.append(f.result())
            except HTTPException as e:
                errors.append(e)

    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0].status_code == 409

    check_db = SessionLocal()
    try:
        final_job = check_db.get(Job, job_id)
        assert final_job.status in ("published", "draft")
        assert final_job.version == 2
    finally:
        check_db.close()


def test_idempotent_approve_already_published_job():
    """Gọi duyệt lần 2 cho tin đã published: bị từ chối 409 INVALID_TRANSITION, không thêm dữ liệu thừa."""
    emp_id, admin1_id, _, job_id = setup_concurrent_fixture()
    db = SessionLocal()
    try:
        approve_job_service(db, job_id, admin1_id, expected_version=1)

        # Lần 2
        with pytest.raises(HTTPException) as exc:
            approve_job_service(db, job_id, admin1_id, expected_version=2)
        assert exc.value.status_code == 409
        assert exc.value.detail == "INVALID_TRANSITION"

        histories = db.query(JobStatusHistory).filter_by(job_id=job_id).all()
        assert len(histories) == 1
    finally:
        db.close()
