"""Integration tests cho luồng duyệt tin tuyển dụng với database thật (Lớp B)."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.company import Company, CompanyStatus
from app.models.job import Job
from app.models.job_status_history import JobStatusHistory
from app.models.notification import Notification
from app.models.user import User
from app.services.job_moderation_service import (
    approve_job_service,
    reject_job_service,
    submit_job_for_review_service,
    withdraw_job_to_draft_service,
)
from app.db.migrations.job_moderation_migration import run_job_moderation_migration


@pytest.fixture
def db_session():
    """Tạo session database cho test và rollback/clean an toàn."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def create_test_employer_and_company(db, verified=True):
    """Factory helper tạo employer và company gọn gàng."""
    tag = uuid.uuid4().hex[:8]
    user = User(
        email=f"emp_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name=f"Employer {tag}",
        role="employer",
        is_active=True,
    )
    db.add(user)
    db.flush()

    v_status = "da_xac_minh" if verified else "chua_xac_minh"
    c_status = CompanyStatus.VERIFIED if verified else CompanyStatus.PENDING
    company = Company(
        employer_id=user.id,
        name=f"Công ty {tag}",
        tax_code=f"010{tag[:7]}",
        address="Hà Nội",
        verification_status=v_status,
        status=c_status,
        is_verified=verified,
    )
    db.add(company)
    db.flush()
    return user, company


def create_test_admin(db):
    """Factory helper tạo admin gọn gàng."""
    tag = uuid.uuid4().hex[:8]
    admin = User(
        email=f"admin_{tag}@test.com",
        password=hash_password("Pass123@"),
        full_name=f"Admin {tag}",
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()
    return admin


def test_approve_job_success_integration(db_session):
    """Duyệt: status thành published, version tăng 1, có 1 lịch sử, có 1 thông báo."""
    emp, comp = create_test_employer_and_company(db_session, verified=True)
    admin = create_test_admin(db_session)

    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title="Kỹ sư Backend Python",
        status="pending",
        version=1,
        deadline=date.today() + timedelta(days=30),
    )
    db_session.add(job)
    db_session.commit()

    updated_job = approve_job_service(
        db=db_session,
        job_id=job.id,
        admin_id=admin.id,
        expected_version=1,
    )

    assert updated_job.status == "published"
    assert updated_job.version == 2
    assert updated_job.reviewed_at is not None

    # Kiểm tra đúng 1 dòng lịch sử
    histories = db_session.query(JobStatusHistory).filter_by(job_id=job.id).all()
    assert len(histories) == 1
    assert histories[0].from_status == "pending"
    assert histories[0].to_status == "published"
    assert histories[0].changed_by == admin.id

    # Kiểm tra đúng 1 thông báo tới employer
    notifs = db_session.query(Notification).filter_by(user_id=emp.id).all()
    assert len(notifs) == 1
    assert "đã được duyệt" in notifs[0].message or "phê duyệt" in notifs[0].message


def test_reject_job_success_integration(db_session):
    """Từ chối: lưu review_note, reviewed_at, lịch sử ghi lý do, gửi thông báo."""
    emp, comp = create_test_employer_and_company(db_session, verified=True)
    admin = create_test_admin(db_session)

    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title="Kỹ sư Frontend React",
        status="pending",
        version=1,
    )
    db_session.add(job)
    db_session.commit()

    reason = "Mô tả công việc thiếu quyền lợi bảo hiểm và địa điểm làm việc."
    updated_job = reject_job_service(
        db=db_session,
        job_id=job.id,
        admin_id=admin.id,
        expected_version=1,
        reason=reason,
    )

    assert updated_job.status == "rejected"
    assert updated_job.version == 2
    assert updated_job.review_note == reason
    assert updated_job.reviewed_at is not None

    histories = db_session.query(JobStatusHistory).filter_by(job_id=job.id).all()
    assert len(histories) == 1
    assert histories[0].to_status == "rejected"
    assert histories[0].reason == reason


def test_transaction_atomic_rollback_on_notification_failure(db_session, monkeypatch):
    """Giả lập lỗi ghi thông báo: kiểm tra jobs không đổi trạng thái và không có lịch sử nào."""
    emp, comp = create_test_employer_and_company(db_session, verified=True)
    admin = create_test_admin(db_session)

    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title="Chuyên viên DevOps",
        status="pending",
        version=1,
    )
    db_session.add(job)
    db_session.commit()

    def mock_broken_notification(*args, **kwargs):
        raise RuntimeError("Simulated notification service failure!")

    monkeypatch.setattr("app.services.job_moderation_service._send_moderation_notification", mock_broken_notification)

    with pytest.raises(RuntimeError):
        approve_job_service(
            db=db_session,
            job_id=job.id,
            admin_id=admin.id,
            expected_version=1,
        )

    # Đảm bảo rollback sạch
    db_session.rollback()
    reloaded_job = db_session.get(Job, job.id)
    assert reloaded_job.status == "pending"
    assert reloaded_job.version == 1

    histories = db_session.query(JobStatusHistory).filter_by(job_id=job.id).all()
    assert len(histories) == 0


def test_submit_job_unverified_company_rejected(db_session):
    """Gửi duyệt khi công ty chưa xác minh: trả lỗi COMPANY_NOT_VERIFIED, status giữ draft."""
    emp, comp = create_test_employer_and_company(db_session, verified=False)

    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title="Thực tập sinh Marketing",
        status="draft",
        version=1,
    )
    db_session.add(job)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        submit_job_for_review_service(
            db=db_session,
            job_id=job.id,
            employer_id=emp.id,
            expected_version=1,
        )
    assert exc.value.status_code == 400
    assert "COMPANY_NOT_VERIFIED" in str(exc.value.detail)

    reloaded = db_session.get(Job, job.id)
    assert reloaded.status == "draft"


def test_migration_idempotent_existing_data(db_session):
    """Chạy migration trên DB có dữ liệu: dòng cũ có version=1, chạy lần hai không lỗi."""
    emp, comp = create_test_employer_and_company(db_session, verified=True)
    job = Job(
        employer_id=emp.id,
        company_id=comp.id,
        title="Tester QA Lead",
        status="draft",
    )
    db_session.add(job)
    db_session.commit()

    # Chạy migration lần 1
    run_job_moderation_migration(db_session.get_bind())
    reloaded = db_session.get(Job, job.id)
    assert reloaded.version == 1

    # Chạy migration lần 2 (idempotent)
    run_job_moderation_migration(db_session.get_bind())
    assert reloaded.version == 1


def test_withdraw_job_success_and_errors(db_session):
    """Test rút tin về nháp thành công và các mã lỗi 404, 403."""
    emp, comp = create_test_employer_and_company(db_session, verified=True)
    job = Job(employer_id=emp.id, company_id=comp.id, title="Test Job", status="pending", version=1)
    db_session.add(job)
    db_session.commit()

    with pytest.raises(HTTPException) as e404:
        withdraw_job_to_draft_service(db_session, 999999, emp.id, 1)
    assert e404.value.status_code == 404

    with pytest.raises(HTTPException) as e403:
        withdraw_job_to_draft_service(db_session, job.id, 999999, 1)
    assert e403.value.status_code == 403

    w = withdraw_job_to_draft_service(db_session, job.id, emp.id, 1)
    assert w.status == "draft"
    assert w.version == 2


def test_approve_reject_not_found(db_session):
    """Test approve và reject với job_id không tồn tại (404)."""
    admin = create_test_admin(db_session)
    with pytest.raises(HTTPException) as e1:
        approve_job_service(db_session, 999999, admin.id, 1)
    assert e1.value.status_code == 404

    with pytest.raises(HTTPException) as e2:
        reject_job_service(db_session, 999999, admin.id, 1, "Reason long enough")
    assert e2.value.status_code == 404
